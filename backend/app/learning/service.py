from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from app.core.config import Settings
from app.learning.models import ModelVersion
from app.learning.persistence import ModelPersistenceError, SupabaseModelRepository
from app.learning.validation import evaluate_weights, walk_forward_weight_validation
from app.learning.versioning import PromotionPolicy
from app.learning.weights import AdaptiveWeightLearner, FactorObservation, WeightLearningConfig

DEFAULT_WEIGHTS = {"htf_trend":0.25,"momentum":0.25,"volume_confirmation":0.15,"market_structure":0.20,"news_sentiment":0.15}


class LearningService:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.repository = SupabaseModelRepository(settings)
        self.learner = AdaptiveWeightLearner(WeightLearningConfig())

    async def active_weights(self) -> tuple[dict[str,float],str|None]:
        try:
            active = await self.repository.active_model(self.settings.model_family)
        except ModelPersistenceError:
            return dict(DEFAULT_WEIGHTS), None
        return (dict(active.weights),active.version_id) if active else (dict(DEFAULT_WEIGHTS),None)

    async def learn_candidate(self) -> ModelVersion:
        records = await self.repository.signal_outcomes()
        if len(records) < 100:
            raise ModelPersistenceError("At least 100 resolved signal outcomes are required")
        active = await self.repository.active_model(self.settings.model_family)
        current = active.weights if active else DEFAULT_WEIGHTS
        train = records[:int(len(records)*0.8)]
        observations = [FactorObservation(factor,score,record.outcome_return_pct,record.regime) for record in train for factor,score in record.factor_scores.items()]
        candidate_weights = self.learner.propose_weights(current,observations)
        version = ModelVersion(f"{self.settings.model_family}-{uuid4().hex[:12]}",self.settings.model_family,datetime.now(timezone.utc),"DRAFT",candidate_weights,active.version_id if active else None,len(train),0,{},self._checksum(candidate_weights))
        return await self.repository.create_candidate(version)

    async def validate_candidate(self, version_id: str) -> ModelVersion:
        candidate = await self.repository.get_model(version_id)
        if candidate is None or candidate.status.value != "DRAFT":
            raise ModelPersistenceError("Only draft candidates can be validated")
        records = await self.repository.signal_outcomes()
        if len(records) < 100:
            raise ModelPersistenceError("At least 100 resolved signal outcomes are required")
        active = await self.repository.active_model(self.settings.model_family)
        baseline = active.weights if active else DEFAULT_WEIGHTS
        windows = walk_forward_weight_validation(records,self.learner,baseline,train_size=min(100,max(20,len(records)//2)),test_size=min(25,max(10,len(records)//5)),step_size=max(10,min(25,len(records)//5)))
        if not windows:
            raise ModelPersistenceError("No complete walk-forward windows are available")
        oos_expectancy = sum(w.oos_expectancy_pct for w in windows)/len(windows)
        oos_hit_rate = sum(w.oos_hit_rate_pct for w in windows)/len(windows)
        holdout = records[-max(25,len(records)//5):]
        holdout_expectancy, holdout_hit_rate = evaluate_weights(holdout,candidate.weights)
        metrics={"walk_forward_windows":float(len(windows)),"oos_expectancy_pct":oos_expectancy,"oos_hit_rate_pct":oos_hit_rate,"candidate_holdout_expectancy_pct":holdout_expectancy,"candidate_holdout_hit_rate_pct":holdout_hit_rate}
        oos_count=sum(w.oos_observations for w in windows)
        await self.repository.update_validation(version_id,oos_count,metrics)
        validated = ModelVersion(candidate.version_id,candidate.model_family,candidate.created_at,candidate.status,candidate.weights,candidate.parent_version_id,candidate.training_observations,oos_count,metrics,candidate.artifact_checksum)
        if not PromotionPolicy(min_oos_observations=50,min_oos_expectancy_pct=0.0).qualifies(validated):
            raise ModelPersistenceError("Candidate failed walk-forward OOS promotion criteria")
        return await self.repository.mark_validated(version_id)

    async def activate(self, version_id: str) -> ModelVersion:
        return await self.repository.activate(version_id)

    @staticmethod
    def _checksum(weights: dict[str,float]) -> str:
        import hashlib,json
        return hashlib.sha256(json.dumps(weights,sort_keys=True,separators=(",",":")).encode()).hexdigest()
