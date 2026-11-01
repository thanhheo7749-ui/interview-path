"""The gap list: unanswered questions grouped by topic, as documents HR should write."""
from dataclasses import dataclass

import numpy as np
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.ai.config import get_config
from app.brain import vectors
from app.database.sql_models import AssistantQuestion

GROUP_COSINE = 0.80


@dataclass(frozen=True)
class GapGroup:
    group_id: int
    sample_question: str
    count: int
    question_ids: tuple[int, ...]


def _same_topic(vector: np.ndarray, seed: np.ndarray) -> bool:
    return vector.size == seed.size and float(vectors.cosine_matrix(vector, seed[np.newaxis, :])[0]) >= GROUP_COSINE


def _clusters(db: Session, company_id: int) -> list[GapGroup]:
    rows = (
        db.query(AssistantQuestion.id, AssistantQuestion.question, AssistantQuestion.embedding,
                 AssistantQuestion.embedding_model)
        .filter(AssistantQuestion.company_id == company_id, AssistantQuestion.answered.is_(False),
                AssistantQuestion.resolved.is_(False),
                # A failure is the system's, not the knowledge's. Older rows have no state and still count.
                or_(AssistantQuestion.state.is_(None), AssistantQuestion.state != "failed"))
        .order_by(AssistantQuestion.id)
        .all()
    )
    model = get_config().slot("embedding").model
    seeds: list[tuple[int, np.ndarray]] = []  # only vectors of the current model are ever compared
    members: dict[int, list[int]] = {}
    samples: dict[int, str] = {}
    for row in rows:
        comparable = row.embedding is not None and row.embedding_model == model
        vector = vectors.decode(row.embedding) if comparable else None
        seed_id = next((seed for seed, seed_vector in seeds if comparable and _same_topic(vector, seed_vector)), None)
        if seed_id is None:
            seed_id = row.id
            samples[row.id] = row.question
            members[row.id] = []
            if comparable:
                seeds.append((row.id, vector))
        members[seed_id].append(row.id)
    return [GapGroup(seed, samples[seed], len(ids), tuple(ids)) for seed, ids in members.items()]


def list_gaps(db: Session, company_id: int) -> list[GapGroup]:
    return sorted(_clusters(db, company_id), key=lambda group: (-group.count, group.group_id))


def resolve_group(db: Session, company_id: int, group_id: int) -> int:
    """Mark a group's questions resolved and return how many. 0 means no such group in this company."""
    group = next((group for group in _clusters(db, company_id) if group.group_id == group_id), None)
    if group is None:
        return 0
    db.query(AssistantQuestion).filter(
        AssistantQuestion.company_id == company_id, AssistantQuestion.id.in_(group.question_ids)
    ).update({AssistantQuestion.resolved: True}, synchronize_session=False)
    db.commit()
    return group.count
