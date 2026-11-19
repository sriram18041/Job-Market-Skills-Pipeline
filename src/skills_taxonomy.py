"""
Skill taxonomy used by the transform stage to detect which in-demand
skills appear in a job posting's title, tags, and description.

Keys are the canonical skill name we store/report. Values are a list of
surface forms (regex-escaped at match time) that should count as a match.
Keep each list short and specific to avoid false positives (e.g. "R" is
deliberately left out because it matches too much incidental text).
"""

SKILLS_TAXONOMY: dict[str, list[str]] = {
    # Languages
    "Python": ["python"],
    "Java": ["java(?!script)"],
    "JavaScript": ["javascript", "js\\b"],
    "TypeScript": ["typescript", "\\bts\\b"],
    "SQL": ["\\bsql\\b"],
    "Scala": ["scala"],
    "C#": ["c#", "\\bc sharp\\b"],
    "Go": ["\\bgolang\\b", "\\bgo\\b"],

    # Data engineering / ETL
    "ETL": ["\\betl\\b", "extract.?transform.?load"],
    "Spark": ["\\bspark\\b", "pyspark"],
    "Databricks": ["databricks"],
    "Airflow": ["airflow"],
    "dbt": ["\\bdbt\\b"],
    "Data Warehousing": ["data warehous"],
    "Data Modeling": ["data model"],
    "Kafka": ["kafka"],

    # Cloud
    "AWS": ["\\baws\\b", "amazon web services"],
    "Azure": ["\\bazure\\b"],
    "GCP": ["\\bgcp\\b", "google cloud"],

    # DevOps / CI-CD
    "Docker": ["docker", "container"],
    "Kubernetes": ["kubernetes", "\\bk8s\\b"],
    "CI/CD": ["ci/cd", "ci\\\\cd", "continuous integration", "continuous deployment", "continuous delivery"],
    "Terraform": ["terraform"],
    "Jenkins": ["jenkins"],
    "GitHub Actions": ["github actions"],

    # Databases
    "PostgreSQL": ["postgres"],
    "MySQL": ["mysql"],
    "MongoDB": ["mongodb", "mongo\\b"],
    "DynamoDB": ["dynamodb"],

    # BI / Analytics
    "Power BI": ["power ?bi"],
    "Tableau": ["tableau"],

    # Web / frameworks
    "React": ["react"],
    "Node.js": ["node\\.?js"],
    ".NET": ["\\.net\\b"],
    "Spring Boot": ["spring boot", "spring mvc"],

    # AI / ML
    "Machine Learning": ["machine learning", "\\bml\\b"],
    "LLM": ["\\bllm\\b", "large language model"],
    "Generative AI": ["generative ai", "genai"],

    # Practices
    "Agile": ["agile", "scrum", "kanban"],
    "Git": ["\\bgit\\b"],
}
