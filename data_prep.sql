-- MySQL data preparation pipeline for the two dataset folders.
-- Run from a MySQL client that has LOCAL INFILE enabled. If MySQL rejects
-- LOCAL INFILE, enable it in both the client connection and MySQL server.
-- Update the paths below if this repository is stored somewhere else.

CREATE DATABASE IF NOT EXISTS workforce_analytics
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;
USE workforce_analytics;

-- Raw staging tables keep CSV values as text so parsing and type conversion
-- happen explicitly in the curated tables below.
CREATE TABLE IF NOT EXISTS stg_employees (
  employee_id LONGTEXT,
  employee_name LONGTEXT,
  age LONGTEXT,
  gender LONGTEXT,
  location LONGTEXT,
  department LONGTEXT,
  job_role LONGTEXT,
  employment_type LONGTEXT,
  experience_years LONGTEXT,
  seniority LONGTEXT,
  availability_pct LONGTEXT,
  current_allocation_pct LONGTEXT,
  performance_score LONGTEXT,
  monthly_salary_lakh LONGTEXT,
  willing_to_relocate LONGTEXT
);

CREATE TABLE IF NOT EXISTS stg_employee_skills (
  employee_id LONGTEXT,
  skill LONGTEXT,
  proficiency_1_5 LONGTEXT,
  skill_experience_years LONGTEXT
);

CREATE TABLE IF NOT EXISTS stg_projects (
  project_id LONGTEXT,
  project_name LONGTEXT,
  domain LONGTEXT,
  location LONGTEXT,
  nearby_locations LONGTEXT,
  start_date LONGTEXT,
  duration_months LONGTEXT,
  team_size_required LONGTEXT,
  priority LONGTEXT,
  budget_lakh LONGTEXT,
  member_allocation_pct LONGTEXT,
  max_relocation_pct LONGTEXT,
  min_lead_count LONGTEXT,
  min_senior_plus_pct LONGTEXT,
  max_lead_pct LONGTEXT,
  max_junior_pct LONGTEXT,
  project_description LONGTEXT,
  oov_tech_mentions LONGTEXT,
  domain_original LONGTEXT,
  budget_lakh_original LONGTEXT
);

CREATE TABLE IF NOT EXISTS stg_project_requirements (
  project_id LONGTEXT,
  required_skill LONGTEXT,
  importance_1_5 LONGTEXT,
  min_proficiency_1_5 LONGTEXT,
  min_experience_years LONGTEXT,
  min_headcount LONGTEXT
);

CREATE TABLE IF NOT EXISTS stg_project_skill_annotations (
  project_id LONGTEXT,
  skill LONGTEXT,
  surface_form LONGTEXT,
  form_type LONGTEXT,
  char_start LONGTEXT,
  char_end LONGTEXT
);

CREATE TABLE IF NOT EXISTS stg_skill_aliases (
  skill LONGTEXT,
  alias LONGTEXT
);

CREATE TABLE IF NOT EXISTS stg_allocation_template (
  allocation_id LONGTEXT,
  project_id LONGTEXT,
  employee_id LONGTEXT,
  match_score LONGTEXT,
  skill_coverage_pct LONGTEXT,
  allocation_pct LONGTEXT,
  relocation_required LONGTEXT,
  optimization_status LONGTEXT
);

-- Load all seven source CSVs. The paths use forward slashes because that form
-- is accepted by MySQL on Windows, including when folder names contain spaces.
TRUNCATE TABLE stg_employees;
TRUNCATE TABLE stg_employee_skills;
TRUNCATE TABLE stg_projects;
TRUNCATE TABLE stg_project_requirements;
TRUNCATE TABLE stg_project_skill_annotations;
TRUNCATE TABLE stg_skill_aliases;
TRUNCATE TABLE stg_allocation_template;

LOAD DATA LOCAL INFILE
  'C:/Users/IDS User/OneDrive/Desktop/workforce/workforce dataset/employees_100k.csv'
INTO TABLE stg_employees
CHARACTER SET utf8mb4
FIELDS TERMINATED BY ',' OPTIONALLY ENCLOSED BY '"' ESCAPED BY '"'
LINES TERMINATED BY '\n'
IGNORE 1 LINES;

LOAD DATA LOCAL INFILE
  'C:/Users/IDS User/OneDrive/Desktop/workforce/workforce dataset/employee_skills.csv'
INTO TABLE stg_employee_skills
CHARACTER SET utf8mb4
FIELDS TERMINATED BY ',' OPTIONALLY ENCLOSED BY '"' ESCAPED BY '"'
LINES TERMINATED BY '\n'
IGNORE 1 LINES;

LOAD DATA LOCAL INFILE
  'C:/Users/IDS User/OneDrive/Desktop/workforce/projects dataset/projects_30_v2.csv'
INTO TABLE stg_projects
CHARACTER SET utf8mb4
FIELDS TERMINATED BY ',' OPTIONALLY ENCLOSED BY '"' ESCAPED BY '"'
LINES TERMINATED BY '\n'
IGNORE 1 LINES;

LOAD DATA LOCAL INFILE
  'C:/Users/IDS User/OneDrive/Desktop/workforce/projects dataset/project_requirements_v2.csv'
INTO TABLE stg_project_requirements
CHARACTER SET utf8mb4
FIELDS TERMINATED BY ',' OPTIONALLY ENCLOSED BY '"' ESCAPED BY '"'
LINES TERMINATED BY '\n'
IGNORE 1 LINES;

LOAD DATA LOCAL INFILE
  'C:/Users/IDS User/OneDrive/Desktop/workforce/projects dataset/project_skill_annotations.csv'
INTO TABLE stg_project_skill_annotations
CHARACTER SET utf8mb4
FIELDS TERMINATED BY ',' OPTIONALLY ENCLOSED BY '"' ESCAPED BY '"'
LINES TERMINATED BY '\n'
IGNORE 1 LINES;

LOAD DATA LOCAL INFILE
  'C:/Users/IDS User/OneDrive/Desktop/workforce/projects dataset/skill_aliases.csv'
INTO TABLE stg_skill_aliases
CHARACTER SET utf8mb4
FIELDS TERMINATED BY ',' OPTIONALLY ENCLOSED BY '"' ESCAPED BY '"'
LINES TERMINATED BY '\n'
IGNORE 1 LINES;

LOAD DATA LOCAL INFILE
  'C:/Users/IDS User/OneDrive/Desktop/workforce/workforce dataset/allocation_template.csv'
INTO TABLE stg_allocation_template
CHARACTER SET utf8mb4
FIELDS TERMINATED BY ',' OPTIONALLY ENCLOSED BY '"' ESCAPED BY '"'
LINES TERMINATED BY '\n'
IGNORE 1 LINES;

-- Curated tables use appropriate types and keys for analysis and joins.
CREATE TABLE IF NOT EXISTS employees (
  employee_id VARCHAR(32) NOT NULL PRIMARY KEY,
  employee_name VARCHAR(255),
  age TINYINT UNSIGNED,
  gender VARCHAR(50),
  location VARCHAR(255),
  department VARCHAR(255),
  job_role VARCHAR(255),
  employment_type VARCHAR(100),
  experience_years DECIMAL(5,1),
  seniority VARCHAR(100),
  availability_pct DECIMAL(5,2),
  current_allocation_pct DECIMAL(5,2),
  performance_score DECIMAL(4,2),
  monthly_salary_lakh DECIMAL(10,2),
  willing_to_relocate BOOLEAN
);

CREATE TABLE IF NOT EXISTS employee_skills (
  employee_id VARCHAR(32) NOT NULL,
  skill VARCHAR(255) NOT NULL,
  proficiency_1_5 TINYINT UNSIGNED,
  skill_experience_years DECIMAL(5,1),
  PRIMARY KEY (employee_id, skill)
);

CREATE TABLE IF NOT EXISTS projects (
  project_id VARCHAR(32) NOT NULL PRIMARY KEY,
  project_name VARCHAR(255),
  domain VARCHAR(255),
  location VARCHAR(255),
  nearby_locations TEXT,
  start_date DATE,
  duration_months SMALLINT UNSIGNED,
  team_size_required SMALLINT UNSIGNED,
  priority VARCHAR(50),
  budget_lakh DECIMAL(12,2),
  member_allocation_pct DECIMAL(5,2),
  max_relocation_pct DECIMAL(5,2),
  min_lead_count SMALLINT UNSIGNED,
  min_senior_plus_pct DECIMAL(5,2),
  max_lead_pct DECIMAL(5,2),
  max_junior_pct DECIMAL(5,2),
  project_description TEXT,
  oov_tech_mentions TEXT,
  domain_original VARCHAR(255),
  budget_lakh_original DECIMAL(12,2)
);

CREATE TABLE IF NOT EXISTS project_requirements (
  project_id VARCHAR(32) NOT NULL,
  required_skill VARCHAR(255) NOT NULL,
  importance_1_5 TINYINT UNSIGNED,
  min_proficiency_1_5 TINYINT UNSIGNED,
  min_experience_years DECIMAL(5,1),
  min_headcount SMALLINT UNSIGNED,
  PRIMARY KEY (project_id, required_skill)
);

CREATE TABLE IF NOT EXISTS project_skill_annotations (
  annotation_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
  project_id VARCHAR(32),
  skill VARCHAR(255),
  surface_form VARCHAR(255),
  form_type VARCHAR(100),
  char_start INT UNSIGNED,
  char_end INT UNSIGNED
);

CREATE TABLE IF NOT EXISTS skill_aliases (
  skill VARCHAR(255) NOT NULL,
  alias VARCHAR(255) NOT NULL,
  PRIMARY KEY (skill, alias)
);

CREATE TABLE IF NOT EXISTS allocation_template (
  allocation_id VARCHAR(64),
  project_id VARCHAR(32),
  employee_id VARCHAR(32),
  match_score DECIMAL(8,5),
  skill_coverage_pct DECIMAL(5,2),
  allocation_pct DECIMAL(5,2),
  relocation_required BOOLEAN,
  optimization_status VARCHAR(100)
);

TRUNCATE TABLE employees;
TRUNCATE TABLE employee_skills;
TRUNCATE TABLE projects;
TRUNCATE TABLE project_requirements;
TRUNCATE TABLE project_skill_annotations;
TRUNCATE TABLE skill_aliases;
TRUNCATE TABLE allocation_template;

INSERT INTO employees (
  employee_id, employee_name, age, gender, location, department, job_role,
  employment_type, experience_years, seniority, availability_pct,
  current_allocation_pct, performance_score, monthly_salary_lakh,
  willing_to_relocate
)
SELECT
  NULLIF(TRIM(employee_id), ''),
  NULLIF(TRIM(employee_name), ''),
  CAST(NULLIF(TRIM(age), '') AS UNSIGNED),
  NULLIF(TRIM(gender), ''),
  NULLIF(TRIM(location), ''),
  NULLIF(TRIM(department), ''),
  NULLIF(TRIM(job_role), ''),
  NULLIF(TRIM(employment_type), ''),
  CAST(NULLIF(TRIM(experience_years), '') AS DECIMAL(5,1)),
  NULLIF(TRIM(seniority), ''),
  CAST(NULLIF(TRIM(availability_pct), '') AS DECIMAL(5,2)),
  CAST(NULLIF(TRIM(current_allocation_pct), '') AS DECIMAL(5,2)),
  CAST(NULLIF(TRIM(performance_score), '') AS DECIMAL(4,2)),
  CAST(NULLIF(TRIM(monthly_salary_lakh), '') AS DECIMAL(10,2)),
  CASE LOWER(TRIM(willing_to_relocate))
    WHEN 'true' THEN TRUE
    WHEN '1' THEN TRUE
    WHEN 'false' THEN FALSE
    WHEN '0' THEN FALSE
    ELSE NULL
  END
FROM stg_employees;

INSERT INTO employee_skills (
  employee_id, skill, proficiency_1_5, skill_experience_years
)
SELECT
  NULLIF(TRIM(employee_id), ''),
  NULLIF(TRIM(skill), ''),
  CAST(NULLIF(TRIM(proficiency_1_5), '') AS UNSIGNED),
  CAST(NULLIF(TRIM(skill_experience_years), '') AS DECIMAL(5,1))
FROM stg_employee_skills;

INSERT INTO projects (
  project_id, project_name, domain, location, nearby_locations, start_date,
  duration_months, team_size_required, priority, budget_lakh,
  member_allocation_pct, max_relocation_pct, min_lead_count,
  min_senior_plus_pct, max_lead_pct, max_junior_pct, project_description,
  oov_tech_mentions, domain_original, budget_lakh_original
)
SELECT
  NULLIF(TRIM(project_id), ''),
  NULLIF(TRIM(project_name), ''),
  NULLIF(TRIM(domain), ''),
  NULLIF(TRIM(location), ''),
  NULLIF(TRIM(nearby_locations), ''),
  STR_TO_DATE(NULLIF(TRIM(start_date), ''), '%Y-%m-%d'),
  CAST(NULLIF(TRIM(duration_months), '') AS UNSIGNED),
  CAST(NULLIF(TRIM(team_size_required), '') AS UNSIGNED),
  NULLIF(TRIM(priority), ''),
  CAST(NULLIF(TRIM(budget_lakh), '') AS DECIMAL(12,2)),
  CAST(NULLIF(TRIM(member_allocation_pct), '') AS DECIMAL(5,2)),
  CAST(NULLIF(TRIM(max_relocation_pct), '') AS DECIMAL(5,2)),
  CAST(NULLIF(TRIM(min_lead_count), '') AS UNSIGNED),
  CAST(NULLIF(TRIM(min_senior_plus_pct), '') AS DECIMAL(5,2)),
  CAST(NULLIF(TRIM(max_lead_pct), '') AS DECIMAL(5,2)),
  CAST(NULLIF(TRIM(max_junior_pct), '') AS DECIMAL(5,2)),
  NULLIF(TRIM(project_description), ''),
  NULLIF(TRIM(oov_tech_mentions), ''),
  NULLIF(TRIM(domain_original), ''),
  CAST(NULLIF(TRIM(budget_lakh_original), '') AS DECIMAL(12,2))
FROM stg_projects;

INSERT INTO project_requirements (
  project_id, required_skill, importance_1_5, min_proficiency_1_5,
  min_experience_years, min_headcount
)
SELECT
  NULLIF(TRIM(project_id), ''),
  NULLIF(TRIM(required_skill), ''),
  CAST(NULLIF(TRIM(importance_1_5), '') AS UNSIGNED),
  CAST(NULLIF(TRIM(min_proficiency_1_5), '') AS UNSIGNED),
  CAST(NULLIF(TRIM(min_experience_years), '') AS DECIMAL(5,1)),
  CAST(NULLIF(TRIM(min_headcount), '') AS UNSIGNED)
FROM stg_project_requirements;

INSERT INTO project_skill_annotations (
  project_id, skill, surface_form, form_type, char_start, char_end
)
SELECT
  NULLIF(TRIM(project_id), ''),
  NULLIF(TRIM(skill), ''),
  NULLIF(TRIM(surface_form), ''),
  NULLIF(TRIM(form_type), ''),
  CAST(NULLIF(TRIM(char_start), '') AS UNSIGNED),
  CAST(NULLIF(TRIM(char_end), '') AS UNSIGNED)
FROM stg_project_skill_annotations;

INSERT INTO skill_aliases (skill, alias)
SELECT
  NULLIF(TRIM(skill), ''),
  NULLIF(TRIM(alias), '')
FROM stg_skill_aliases;

INSERT INTO allocation_template (
  allocation_id, project_id, employee_id, match_score,
  skill_coverage_pct, allocation_pct, relocation_required,
  optimization_status
)
SELECT
  NULLIF(TRIM(allocation_id), ''),
  NULLIF(TRIM(project_id), ''),
  NULLIF(TRIM(employee_id), ''),
  CAST(NULLIF(TRIM(match_score), '') AS DECIMAL(8,5)),
  CAST(NULLIF(TRIM(skill_coverage_pct), '') AS DECIMAL(5,2)),
  CAST(NULLIF(TRIM(allocation_pct), '') AS DECIMAL(5,2)),
  CASE LOWER(TRIM(relocation_required))
    WHEN 'true' THEN TRUE
    WHEN '1' THEN TRUE
    WHEN 'false' THEN FALSE
    WHEN '0' THEN FALSE
    ELSE NULL
  END,
  NULLIF(TRIM(optimization_status), '')
FROM stg_allocation_template;

-- Validation: source_rows and curated_rows should match for each dataset.
SELECT 'employees' AS dataset,
       (SELECT COUNT(*) FROM stg_employees) AS source_rows,
       (SELECT COUNT(*) FROM employees) AS curated_rows
UNION ALL
SELECT 'employee_skills',
       (SELECT COUNT(*) FROM stg_employee_skills),
       (SELECT COUNT(*) FROM employee_skills)
UNION ALL
SELECT 'projects',
       (SELECT COUNT(*) FROM stg_projects),
       (SELECT COUNT(*) FROM projects)
UNION ALL
SELECT 'project_requirements',
       (SELECT COUNT(*) FROM stg_project_requirements),
       (SELECT COUNT(*) FROM project_requirements)
UNION ALL
SELECT 'project_skill_annotations',
       (SELECT COUNT(*) FROM stg_project_skill_annotations),
       (SELECT COUNT(*) FROM project_skill_annotations)
UNION ALL
SELECT 'skill_aliases',
       (SELECT COUNT(*) FROM stg_skill_aliases),
       (SELECT COUNT(*) FROM skill_aliases)
UNION ALL
SELECT 'allocation_template',
       (SELECT COUNT(*) FROM stg_allocation_template),
       (SELECT COUNT(*) FROM allocation_template);

-- Validation: these counts should be zero. Investigate any non-zero results.
SELECT 'employee skills without employee' AS check_name, COUNT(*) AS problem_rows
FROM employee_skills s
LEFT JOIN employees e ON e.employee_id = s.employee_id
WHERE e.employee_id IS NULL
UNION ALL
SELECT 'requirements without project', COUNT(*)
FROM project_requirements r
LEFT JOIN projects p ON p.project_id = r.project_id
WHERE p.project_id IS NULL
UNION ALL
SELECT 'annotations without project', COUNT(*)
FROM project_skill_annotations a
LEFT JOIN projects p ON p.project_id = a.project_id
WHERE p.project_id IS NULL;
