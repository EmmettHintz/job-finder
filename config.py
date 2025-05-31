"""
Configuration settings for the Enhanced Job Finder
"""

# Job search settings
JOB_SEARCH_CONFIG = {
    "max_parallel_searches": 5,
    "page_timeout": 30000,  # milliseconds
    "rate_limit_delay": 2,  # seconds between batches
    "max_results_per_board": 50,
    "recent_jobs_only": True,  # Focus on jobs posted within last 30 days
}

# LLM settings
LLM_CONFIG = {
    "provider": "openai/gpt-4.1-nano",
    "max_retries": 3,
    "temperature": 0.1,  # Low temperature for consistent extraction
    "max_tokens": 4000,
}

# Connection finding settings
CONNECTION_CONFIG = {
    "max_connections_per_job": 20,
    "min_relevance_score": 0.3,
    "search_timeout": 20000,  # milliseconds
    "linkedin_searches_per_job": 3,
}

# Browser settings
BROWSER_CONFIG = {
    "headless": True,
    "viewport_width": 1920,
    "viewport_height": 1080,
    "user_agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "javascript_enabled": True,
    "images_enabled": False,  # Faster loading
}

# Logging settings
LOGGING_CONFIG = {
    "level": "INFO",
    "format": "%(asctime)s - %(levelname)s - %(message)s",
    "file": "job_finder.log",
    "max_file_size": 10 * 1024 * 1024,  # 10MB
    "backup_count": 5,
}

# Output settings
OUTPUT_CONFIG = {
    "directory": "output",
    "filename_format": "job_search_results_{timestamp}.json",
    "include_metadata": True,
    "pretty_print": True,
    "encoding": "utf-8",
}

# Job filtering settings
FILTER_CONFIG = {
    "spam_keywords": [
        "similar jobs", "related jobs", "more jobs", "view all",
        "job alert", "email alert", "save search", "job search",
        "sign up", "create account", "login", "register"
    ],
    "min_job_title_length": 3,
    "min_company_name_length": 2,
    "required_fields": ["job_title", "company_name"],
}

# Additional job boards (can be easily extended)
ADDITIONAL_JOB_BOARDS = [
    # Add more job boards here following the JobBoard pattern
    # {
    #     "name": "CustomBoard",
    #     "base_url": "https://customboard.com",
    #     "search_pattern": "/jobs?q={keywords}&location={location}",
    #     "extraction_config": {
    #         "job_selector": ".job",
    #         "title_selector": ".title",
    #         "company_selector": ".company",
    #         "location_selector": ".location",
    #         "link_selector": ".link"
    #     }
    # }
]

# Skills categorization for better parsing
SKILL_CATEGORIES = {
    "programming_languages": [
        "python", "javascript", "java", "c++", "c#", "go", "rust", "swift",
        "kotlin", "php", "ruby", "typescript", "scala", "r", "matlab"
    ],
    "web_technologies": [
        "react", "angular", "vue", "node.js", "express", "django", "flask",
        "spring", "laravel", "rails", "html", "css", "sass", "less"
    ],
    "databases": [
        "sql", "mysql", "postgresql", "mongodb", "redis", "elasticsearch",
        "oracle", "sqlite", "cassandra", "dynamodb"
    ],
    "cloud_platforms": [
        "aws", "azure", "gcp", "google cloud", "heroku", "digitalocean",
        "kubernetes", "docker", "terraform", "ansible"
    ],
    "data_science": [
        "machine learning", "deep learning", "pandas", "numpy", "scikit-learn",
        "tensorflow", "pytorch", "spark", "hadoop", "tableau", "power bi"
    ],
    "mobile": [
        "ios", "android", "react native", "flutter", "xamarin", "ionic",
        "swift", "kotlin", "objective-c"
    ]
}

# Experience level mapping
EXPERIENCE_LEVELS = {
    "entry": ["entry", "junior", "associate", "graduate", "intern", "trainee"],
    "mid": ["mid", "intermediate", "regular", "standard"],
    "senior": ["senior", "lead", "principal", "staff", "architect"],
    "executive": ["director", "vp", "cto", "ceo", "head", "chief", "manager"]
}

# Location standardization
LOCATION_MAPPINGS = {
    "remote_keywords": ["remote", "work from home", "wfh", "telecommute", "distributed"],
    "hybrid_keywords": ["hybrid", "flexible", "mix", "partial remote"],
    "major_cities": {
        "sf": "San Francisco, CA",
        "nyc": "New York, NY",
        "la": "Los Angeles, CA",
        "chicago": "Chicago, IL",
        "boston": "Boston, MA",
        "seattle": "Seattle, WA",
        "austin": "Austin, TX",
        "denver": "Denver, CO"
    }
}

# Email and social media patterns for contact finding
CONTACT_PATTERNS = {
    "email_domains": [
        "@gmail.com", "@outlook.com", "@hotmail.com", "@yahoo.com",
        "@company.com"  # Will be replaced with actual company domain
    ],
    "linkedin_patterns": [
        "linkedin.com/in/",
        "linkedin.com/pub/"
    ],
    "github_patterns": [
        "github.com/",
        "github.io"
    ],
    "twitter_patterns": [
        "twitter.com/",
        "x.com/"
    ]
}

# Rate limiting and request delays
RATE_LIMITS = {
    "requests_per_minute": 30,
    "delay_between_requests": 2,  # seconds
    "max_concurrent_requests": 5,
    "exponential_backoff": True,
    "max_retry_delay": 60,  # seconds
}

# Search optimization
SEARCH_OPTIMIZATION = {
    "use_synonyms": True,
    "expand_location_search": True,
    "include_related_titles": True,
    "boost_recent_postings": True,
    "filter_duplicates": True,
    "relevance_threshold": 0.7
} 