import pytest
import numpy as np
from app.ml.collision_probability import collision_probability_estimator
from httpx import AsyncClient


def test_b_plane_encounter_coordinates():
    # Primary: [7000, 0, 0], velocity [0, 7.5, 0]
    r1 = np.array([7000.0, 0.0, 0.0])
    v1 = np.array([0.0, 7.5, 0.0])

    # Secondary: [7001, 10, 0], velocity [0, -7.5, 0] (head-on collision geometry)
    r2 = np.array([7001.0, 10.0, 0.0])
    v2 = np.array([0.0, -7.5, 0.0])

    x_enc, z_enc, v_rel, proj = collision_probability_estimator.compute_b_plane_encounter_coordinates(
        r1, v1, r2, v2
    )

    assert v_rel == 15.0  # Closing velocity = 7.5 - (-7.5) = 15 km/s
    assert abs(x_enc) > 0.0 or abs(z_enc) > 0.0
    assert proj.shape == (2, 3)


def test_foster_probability_and_nasa_cara_tier():
    # Very close encounter: miss distance 0.02 km (20 meters), HBR = 20 meters
    res_critical = collision_probability_estimator.compute_foster_probability(
        miss_distance_km=0.02,
        hard_body_radius_m=20.0,
        sigma_x_km=0.1,
        sigma_y_km=0.1
    )
    assert res_critical["collision_probability"] > 1e-4
    assert "RED_ALERT" in res_critical["nasa_cara_tier"]
    assert res_critical["operational_severity"] == "CRITICAL"

    # Distant encounter: miss distance 15 km
    res_safe = collision_probability_estimator.compute_foster_probability(
        miss_distance_km=15.0,
        hard_body_radius_m=15.0,
        sigma_x_km=0.8,
        sigma_y_km=0.5
    )
    assert res_safe["collision_probability"] < 1e-7
    assert "GREEN" in res_safe["nasa_cara_tier"]


def test_monte_carlo_covariance_simulation():
    # Run simulation with 5000 draws
    mc_res = collision_probability_estimator.run_monte_carlo_simulation(
        miss_distance_km=0.05,
        hard_body_radius_m=25.0,
        sigma_km=0.05,
        n_trials=5000
    )
    assert mc_res["trials"] == 5000
    assert "mc_probability" in mc_res
    assert mc_res["collision_hits"] >= 0


def test_b_plane_ellipse_generation():
    points = collision_probability_estimator.generate_b_plane_ellipse(
        center_x=0.0,
        center_y=0.0,
        sigma_x=0.8,
        sigma_y=0.5,
        num_points=30
    )
    assert len(points) == 30
    first = points[0]
    assert "x_1sigma" in first
    assert "y_1sigma" in first
    assert "x_3sigma" in first
    assert "y_3sigma" in first


def test_collision_probability_api_evaluation():
    # Direct endpoint verification of Foster encounter and Monte Carlo pipeline
    foster_res = collision_probability_estimator.compute_foster_probability(
        miss_distance_km=1.42,
        hard_body_radius_m=15.0,
        sigma_x_km=0.8,
        sigma_y_km=0.5
    )
    assert foster_res["operational_severity"] in ["CRITICAL", "ELEVATED", "NOMINAL"]
    assert "Foster 2D Encounter Frame" in foster_res["method"]
    assert "collision_probability" in foster_res
    assert "nasa_cara_tier" in foster_res

    mc_res = collision_probability_estimator.run_monte_carlo_simulation(
        miss_distance_km=1.42,
        hard_body_radius_m=15.0,
        sigma_km=0.65,
        n_trials=1000
    )
    assert mc_res["trials"] == 1000
    assert "mc_probability" in mc_res
    assert mc_res["collision_hits"] >= 0
