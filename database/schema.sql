CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

CREATE TABLE projects (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    location_name VARCHAR(255),
    country VARCHAR(100),
    region VARCHAR(100),
    total_area_ha FLOAT,
    project_type VARCHAR(50),
    start_date DATE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE boundaries (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    boundary_geom GEOMETRY(Polygon, 4326),
    area_ha FLOAT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_boundary_geom ON boundaries USING GIST (boundary_geom);

CREATE TABLE observations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    observation_date DATE NOT NULL,
    ndvi FLOAT,
    ndvi_std FLOAT,
    ndvi_count INT,
    evi FLOAT,
    biomass_estimate FLOAT,
    biomass_std FLOAT,
    data_source VARCHAR(100),
    cloud_cover_percent FLOAT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_observation_project_date ON observations (project_id, observation_date);

CREATE TABLE processing_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    operation_type VARCHAR(100),
    status VARCHAR(50),
    input_data JSONB,
    output_data JSONB,
    error_message TEXT,
    execution_time_ms INT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_project_operation ON processing_logs (project_id, operation_type);

CREATE TABLE evidence_packages (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    package_date DATE,
    period_start DATE,
    period_end DATE,
    status VARCHAR(50),
    s3_path VARCHAR(500),
    checksum VARCHAR(64),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_evidence_package_date ON evidence_packages (project_id, package_date);

CREATE TABLE lineage_metadata (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    processing_log_id UUID NOT NULL REFERENCES processing_logs(id) ON DELETE CASCADE,
    satellite_source VARCHAR(100),
    satellite_date DATE,
    script_version VARCHAR(50),
    model_version VARCHAR(50),
    rule_version VARCHAR(50),
    input_parameters JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
