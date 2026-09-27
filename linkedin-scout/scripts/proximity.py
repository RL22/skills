"""
proximity.py - Deterministic Proximity and Warmth Evaluation Engine.
Part of the linkedin-scout skill (scripts/proximity.py).

Implements the 7-Degree Rubric Grading and 4-Tier Contact Ranking models deterministically:
1. Scores individual mutual connection paths (0-100 integer points).
2. Calculates aggregate mutual warmth via diminishing returns (best-path weighting).
3. Assigns exact 1-7 Rubric Degree and WARM/BRIDGE/COLD/FROZEN Action Tier.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import List, Literal, Optional, Tuple
from pydantic import BaseModel, Field

# Ensure schemas can be imported
current_dir = Path(__file__).resolve().parent
if str(current_dir) not in sys.path:
    sys.path.insert(0, str(current_dir))

try:
    from schemas import ContactTier, NetworkDegree, WarmthDegree
except ImportError:
    from .schemas import ContactTier, NetworkDegree, WarmthDegree


class MutualEvaluation(BaseModel):
    """Evaluation result for an individual mutual connection bridge."""

    name: str
    tenure_score: int = Field(ge=0, le=40, description="Score for shared company & overlapping tenure")
    authority_score: int = Field(ge=0, le=25, description="Score for managerial / leadership authority")
    cohort_score: int = Field(ge=0, le=20, description="Score for shared cohort or alumni network")
    domain_score: int = Field(ge=0, le=10, description="Score for engineering / CMS craft alignment")
    activity_score: int = Field(ge=0, le=5, description="Score for recent platform activity")
    total_q: int = Field(ge=0, le=100, description="Composite path proximity score (0-100)")
    category: Literal["anchor", "domain_peer", "low_signal"]


class ContactAssessment(BaseModel):
    """Complete deterministic assessment for a target candidate."""

    candidate_name: str
    degree: NetworkDegree
    warmth_degree: WarmthDegree = Field(ge=1, le=7)
    contact_tier: ContactTier
    aggregate_proximity_score: int = Field(ge=0, le=100)
    breadth_bonus: int = Field(ge=0, le=10)
    primary_mutual: Optional[str] = None
    action_recommendation: str
    rationale: str


def score_single_mutual(
    name: str,
    has_overlapping_tenure: bool = False,
    has_shared_company_non_overlap: bool = False,
    is_former_manager: bool = False,
    is_staff_or_lead: bool = False,
    is_shared_cohort: bool = False,
    is_domain_peer: bool = False,
    is_recently_active: bool = True,
) -> MutualEvaluation:
    """Calculate deterministic integer proximity score (q) for a single mutual connection."""
    # 1. Tenure (max 40)
    tenure = 40 if has_overlapping_tenure else (20 if has_shared_company_non_overlap else 0)

    # 2. Authority (max 25)
    authority = 25 if is_former_manager else (15 if is_staff_or_lead else 0)

    # 3. Cohort (max 20)
    cohort = 20 if is_shared_cohort else 0

    # 4. Domain (max 10)
    domain = 10 if is_domain_peer else 0

    # 5. Activity (max 5)
    activity = 5 if is_recently_active else 0

    total_q = min(100, tenure + authority + cohort + domain + activity)

    category: Literal["anchor", "domain_peer", "low_signal"]
    if total_q >= 75:
        category = "anchor"
    elif total_q >= 45:
        category = "domain_peer"
    else:
        category = "low_signal"

    return MutualEvaluation(
        name=name,
        tenure_score=tenure,
        authority_score=authority,
        cohort_score=cohort,
        domain_score=domain,
        activity_score=activity,
        total_q=total_q,
        category=category,
    )


def compute_breadth_bonus(total_mutual_count: int) -> int:
    """Deterministic lookup for breadth bonus points based on total mutual count."""
    if total_mutual_count >= 10:
        return 10
    if total_mutual_count >= 6:
        return 6
    if total_mutual_count >= 4:
        return 3
    return 0


def aggregate_mutual_proximity(
    mutual_scores: List[int],
    total_mutual_count: int,
) -> int:
    """Aggregate individual scores into a single diminishing-returns score (0-100)."""
    if not mutual_scores:
        return 0

    # Sort descending
    sorted_q = sorted(mutual_scores, reverse=True)

    q1 = sorted_q[0]
    q2 = sorted_q[1] if len(sorted_q) > 1 else 0
    q3 = sorted_q[2] if len(sorted_q) > 2 else 0

    breadth = compute_breadth_bonus(max(total_mutual_count, len(sorted_q)))

    # Normalized path calculation: single mutual gets 100% of its weight, 2 mutuals get 75/25, 3+ get 70/20/10
    if len(sorted_q) == 1:
        weighted = float(q1) + breadth
    elif len(sorted_q) == 2:
        weighted = (0.75 * q1) + (0.25 * q2) + breadth
    else:
        weighted = (0.70 * q1) + (0.20 * q2) + (0.10 * q3) + breadth

    return min(100, int(round(weighted)))


def assess_contact(
    candidate_name: str,
    degree: NetworkDegree,
    is_personal_friend: bool = False,
    is_former_teammate: bool = False,
    mutual_evaluations: Optional[List[MutualEvaluation]] = None,
    total_mutual_count: int = 0,
    has_open_profile: bool = False,
    has_verified_email: bool = False,
) -> ContactAssessment:
    """Deterministically classify a contact into the 7 Rubric Degrees and 4 Action Tiers."""
    mutuals = mutual_evaluations or []
    scores = [m.total_q for m in mutuals]
    agg_score = aggregate_mutual_proximity(scores, max(total_mutual_count, len(mutuals)))

    best_mutual_name: Optional[str] = None
    if mutuals:
        sorted_m = sorted(mutuals, key=lambda m: m.total_q, reverse=True)
        best_mutual_name = sorted_m[0].name

    # Decision Engine
    warmth_degree: WarmthDegree
    contact_tier: ContactTier
    action: str
    rationale: str

    # Tier 1: WARM (Degrees 6 & 7)
    if is_personal_friend or (degree == "1st" and is_former_teammate):
        warmth_degree = 7
        contact_tier = "WARM"
        action = "Personal 1-on-1 outreach (SMS/call/casual DM). Direct referral or routing ask."
        rationale = f"Direct personal relationship with {candidate_name}. Zero cold B2B templates."
    elif degree == "1st":
        warmth_degree = 6
        contact_tier = "WARM"
        action = "LinkedIn Inbox direct message (1-2 paragraphs). Context restoration + update on focus."
        rationale = f"Existing 1st-degree connection with {candidate_name}. Free unmetered messaging."
    elif degree == "2nd" and agg_score >= 75:
        warmth_degree = 6
        contact_tier = "WARM"
        action = f"Request double-opt-in warm introduction from {best_mutual_name or 'mutual leader'}."
        rationale = f"2nd-degree with Anchor Mutual ({best_mutual_name}, score >= 75). High-confidence bridge."

    # Tier 2: BRIDGE (Degrees 4 & 5)
    elif degree == "2nd" and agg_score >= 45:
        warmth_degree = 5
        contact_tier = "BRIDGE"
        action = f"200-char connection note explicitly naming {best_mutual_name or 'shared domain peer'}."
        rationale = f"2nd-degree with Domain Peer mutuals (score {agg_score}). Cite shared peer and craft."
    elif degree == "2nd":
        warmth_degree = 4
        contact_tier = "BRIDGE"
        action = "200-char connection note focused on company/role challenge. Treat mutuals as secondary."
        rationale = f"2nd-degree with loose mutuals (score {agg_score}). Lead with technical relevance."

    # Tier 3: COLD (Degree 3)
    elif has_open_profile or has_verified_email:
        warmth_degree = 3
        contact_tier = "COLD"
        channel_name = "Free InMail (Open Profile)" if has_open_profile else "Verified Corporate Email"
        action = f"Deploy 3-touch Opportunity-Linked Sequence via {channel_name} (Trigger -> Artifact -> Route)."
        rationale = f"3rd-degree/cold, but direct delivery path available via {channel_name}."

    # Tier 4: FROZEN (Degrees 1 & 2)
    elif degree in ("3rd+", "Unknown") and not has_open_profile and not has_verified_email:
        warmth_degree = 2
        contact_tier = "FROZEN"
        action = "Halt outreach. Discover 1st/2nd-degree peers or recruiters at company before using InMail credit."
        rationale = f"Gated 3rd-degree connection with zero mutual path. High friction, low conversion."
    else:
        warmth_degree = 1
        contact_tier = "FROZEN"
        action = "Do not contact. Archive or monitor for organizational triggers."
        rationale = "Unverified or dead-end contact path."

    return ContactAssessment(
        candidate_name=candidate_name,
        degree=degree,
        warmth_degree=warmth_degree,
        contact_tier=contact_tier,
        aggregate_proximity_score=agg_score,
        breadth_bonus=compute_breadth_bonus(max(total_mutual_count, len(mutuals))),
        primary_mutual=best_mutual_name,
        action_recommendation=action,
        rationale=rationale,
    )


if __name__ == "__main__":
    print("Testing Proximity & Warmth Engine...")

    # Case 1: High School Friend (Carol Ferris)
    res_lydia = assess_contact(
        candidate_name="Carol Ferris",
        degree="2nd",
        is_personal_friend=True,
    )
    assert res_lydia.warmth_degree == 7
    assert res_lydia.contact_tier == "WARM"
    print("✓ Case 1 (Personal Friend): Correctly assigned Degree 7 / WARM tier.")

    # Case 2: Umbra EM with former manager mutual (Sam Wilson via Matt Murdock)
    m_steven = score_single_mutual(
        name="Matt Murdock",
        has_overlapping_tenure=True,
        is_former_manager=True,
        is_domain_peer=True,
    )
    assert m_steven.total_q >= 75
    assert m_steven.category == "anchor"

    res_jo = assess_contact(
        candidate_name="Sam Wilson",
        degree="2nd",
        mutual_evaluations=[m_steven],
        total_mutual_count=2,
    )
    assert res_jo.warmth_degree == 6
    assert res_jo.contact_tier == "WARM"
    assert res_jo.primary_mutual == "Matt Murdock"
    print("✓ Case 2 (Anchor Mutual): Correctly elevated to Degree 6 / WARM tier.")

    # Case 3: Verdant EM with Domain Peer mutuals (Tony Stark via Nick Fury)
    m_nick = score_single_mutual(
        name="Nick Fury",
        has_overlapping_tenure=False,
        is_shared_cohort=True,
        is_domain_peer=True,
        is_staff_or_lead=True,
    )
    assert m_nick.category == "domain_peer"

    res_tony = assess_contact(
        candidate_name="Tony Stark",
        degree="2nd",
        mutual_evaluations=[m_nick],
        total_mutual_count=3,
    )
    assert res_tony.warmth_degree == 4 or res_tony.warmth_degree == 5
    assert res_tony.contact_tier == "BRIDGE"
    print(f"✓ Case 3 (Domain Peer Mutual): Correctly assigned Degree {res_tony.warmth_degree} / BRIDGE tier.")

    # Case 4: 3rd-Degree with Open Profile
    res_open = assess_contact(
        candidate_name="Jane Doe",
        degree="3rd+",
        has_open_profile=True,
    )
    assert res_open.warmth_degree == 3
    assert res_open.contact_tier == "COLD"
    print("✓ Case 4 (Open Profile Cold): Correctly assigned Degree 3 / COLD tier.")

    # Case 5: 3rd-Degree Gated
    res_gated = assess_contact(
        candidate_name="John Gated",
        degree="3rd+",
        has_open_profile=False,
    )
    assert res_gated.warmth_degree == 2
    assert res_gated.contact_tier == "FROZEN"
    print("✓ Case 5 (Gated 3rd-Degree): Correctly assigned Degree 2 / FROZEN tier.")

    print("\nALL PROXIMITY & WARMTH TESTS PASSED DETERMINISTICALLY!")
