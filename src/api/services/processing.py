"""
GeoMRV Processing Service
=========================
Placeholder for satellite data processing orchestration.
"""


async def process_satellite_data(project_id: str, start_date: str, end_date: str):
    """
    Orchestrate satellite data fetching and processing.

    This is a stub - actual implementation will use:
    - src.satellite_services.earth_engine_client
    - src.satellite_services.ndvi_calculator
    - src.satellite_services.timelapse_exporter
    """
    raise NotImplementedError("Satellite processing not yet implemented")


async def generate_evidence_package(project_id: str, job_id: str):
    """
    Generate an evidence package for a completed processing job.

    This is a stub - actual implementation in Phase 3.
    """
    raise NotImplementedError("Evidence packaging not yet implemented")
