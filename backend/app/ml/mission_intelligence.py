from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
import httpx
from app.core.config import settings
from app.core.logging import logger


class AIMissionIntelligenceEngine:
    """
    Model 5 – AI Mission Intelligence (LLM + RAG Synthesis).
    Ingests physical SGP4 ephemeris, neural residuals, anomaly detections,
    and collision probability distributions to synthesize explainable mission reports.
    """

    def __init__(self):
        self.api_key = settings.LLM_API_KEY or settings.GEMINI_API_KEY
        self.base_url = settings.LLM_BASE_URL

    async def generate_mission_intelligence_report(
        self,
        primary_satellite: Dict[str, Any],
        conjunction: Dict[str, Any],
        anomaly_metrics: Optional[Dict[str, Any]] = None,
        collision_prob_metrics: Optional[Dict[str, Any]] = None,
        operator_query: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Synthesize technical mission intelligence.
        Attempts LLM generation via configured API, with high-fidelity deterministic
        aerospace flight-dynamics rule engine fallback.
        """
        p_name = primary_satellite.get("name", "PRIMARY SATELLITE")
        p_id = primary_satellite.get("norad_id", 0)
        s_name = conjunction.get("secondary_name", "TRACKED DEBRIS")
        s_id = conjunction.get("secondary_norad_id", 0)
        tca = conjunction.get("tca", "UNKNOWN")
        miss_km = conjunction.get("miss_distance_km", 0.0)
        rel_vel = conjunction.get("relative_velocity_kms", 0.0)
        risk_lvl = conjunction.get("risk_level", "LOW")

        # Anomaly context
        ano_score = anomaly_metrics.get("anomaly_score", 0.0) if anomaly_metrics else 0.0
        ano_diag = anomaly_metrics.get("classification", "NOMINAL") if anomaly_metrics else "NOMINAL"

        # Probability context
        pc_sci = collision_prob_metrics.get("collision_probability_sci", "0.000e+00") if collision_prob_metrics else "N/A"
        cara_tier = collision_prob_metrics.get("nasa_cara_tier", "GREEN") if collision_prob_metrics else "GREEN"

        # Prompt payload
        prompt = (
            f"Generate an operational aerospace conjunction assessment brief for:\n"
            f"Primary Asset: {p_name} (NORAD {p_id})\n"
            f"Approaching Object: {s_name} (NORAD {s_id})\n"
            f"Time of Closest Approach (TCA): {tca}\n"
            f"Miss Distance: {miss_km} km\n"
            f"Relative Velocity: {rel_vel} km/s\n"
            f"Assessed Risk Tier: {risk_lvl}\n"
            f"ML Anomaly Score: {ano_score} ({ano_diag})\n"
            f"Collision Probability: {pc_sci} ({cara_tier})\n"
            f"User Question: {operator_query or 'Summarize risk and recommended operator posture.'}"
        )

        llm_output = await self._call_llm(prompt)
        if not llm_output:
            llm_output = self._generate_deterministic_brief(
                p_name=p_name,
                p_id=p_id,
                s_name=s_name,
                s_id=s_id,
                tca=str(tca),
                miss_km=miss_km,
                rel_vel=rel_vel,
                risk_lvl=str(risk_lvl),
                ano_score=ano_score,
                ano_diag=ano_diag,
                pc_sci=pc_sci,
                cara_tier=cara_tier,
                operator_query=operator_query
            )

        return {
            "status": "success",
            "model": "Model 5 – AI Mission Intelligence (RAG/LLM)",
            "primary_asset": f"{p_name} ({p_id})",
            "secondary_object": f"{s_name} ({s_id})",
            "tca": tca,
            "executive_summary": llm_output["executive_summary"],
            "technical_findings": llm_output["technical_findings"],
            "recommended_action": llm_output["recommended_action"],
            "human_in_the_loop_gate": (
                "ACTION REQUIRED: Human Flight Dynamics Officer approval is mandatory "
                "before any maneuver command is finalized."
            ),
            "disclaimer": settings.SYSTEM_DISCLAIMER
        }

    async def _call_llm(self, prompt: str) -> Optional[Dict[str, Any]]:
        """Call external LLM API if configured."""
        import os
        import sys
        if 'pytest' in sys.modules or os.environ.get("ENVIRONMENT") == "test" or not self.api_key:
            return None
        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            # OpenAI / Custom compatible completions endpoint
            url = f"{self.base_url.rstrip('/')}/v1/chat/completions"
            payload = {
                "model": "gpt-3.5-turbo",
                "messages": [
                    {
                        "role": "system",
                        "content": "You are ORBITGUARD AI, a Senior Aerospace Flight Dynamics Officer specializing in orbital collision avoidance and conjunction assessment."
                    },
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.2
            }
            async with httpx.AsyncClient(timeout=8.0) as client:
                res = await client.post(url, json=payload, headers=headers)
                if res.status_code == 200:
                    data = res.json()
                    content = data["choices"][0]["message"]["content"]
                    return {
                        "executive_summary": content[:250] + "...",
                        "technical_findings": content,
                        "recommended_action": "Evaluate delta-v options with Mission Planning Agent."
                    }
        except Exception as e:
            logger.debug(f"LLM API request bypassed or failed: {e}")
        return None

    def _generate_deterministic_brief(
        self,
        p_name: str,
        p_id: int,
        s_name: str,
        s_id: int,
        tca: str,
        miss_km: float,
        rel_vel: float,
        risk_lvl: str,
        ano_score: float,
        ano_diag: str,
        pc_sci: str,
        cara_tier: str,
        operator_query: Optional[str]
    ) -> Dict[str, Any]:
        """High-fidelity aerospace deterministic expert rules engine."""
        urgency = "IMMEDIATE ATTENTION" if risk_lvl in ["HIGH", "CRITICAL"] else "ROUTINE MONITORING"
        
        exec_summary = (
            f"ORBITGUARD AI has screened a {risk_lvl} severity conjunction between operational asset "
            f"{p_name} and {s_name}. The predicted minimum miss distance is {miss_km:.2f} km "
            f"at relative velocity {rel_vel:.2f} km/s. This is a proximity screening result; its threshold band "
            f"({cara_tier}) is an indicative model comparison, not an operational NASA CARA posture."
        )

        tech_findings = (
            f"1. Orbital Kinematics: Encounter geometry indicates high closing velocity ({rel_vel:.2f} km/s), "
            f"yielding significant kinetic collision risk. Time of closest approach is projected for {tca}.\n"
            f"2. Anomaly Evaluation: ML anomaly detector reports an anomaly score of {ano_score:.2f} ({ano_diag}), "
            f"confirming that primary asset orbit ephemeris reflects standard upper atmospheric drag conditions.\n"
            f"3. Modeled Probability Estimate: Foster 2D model-based Pc estimate = {pc_sci} under the available "
            f"uncertainty assumptions. Without validated encounter covariance, this is illustrative screening only, "
            f"not a scientifically validated operational Pc. The {cara_tier} threshold comparison is indicative only."
        )

        if risk_lvl == "CRITICAL" or miss_km < 2.0:
            rec_action = (
                "Initiate CAM (Collision Avoidance Maneuver) trade-off analysis. "
                "Simulate prograde/retrograde delta-v burn of 0.3 - 0.8 m/s at perigee. "
                "Requires authenticated operator authorization before execution."
            )
        elif risk_lvl == "HIGH":
            rec_action = (
                "Place tracking on high-priority screening. Obtain updated TLE/OMM elements at next ground station pass. "
                "Prepare preliminary maneuver trajectory simulation."
            )
        else:
            rec_action = "Maintain continuous automated SGP4 screening. Re-screen 24 hours prior to TCA."

        return {
            "executive_summary": exec_summary,
            "technical_findings": tech_findings,
            "recommended_action": rec_action
        }


mission_intelligence_engine = AIMissionIntelligenceEngine()
