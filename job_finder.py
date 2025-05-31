import asyncio
import os
import json
import re
import time
from datetime import datetime
from pydantic import BaseModel, Field, field_validator
from typing import List, Optional, Dict, Any, Union
from dotenv import load_dotenv
from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode, LLMConfig
from crawl4ai.extraction_strategy import LLMExtractionStrategy
import logging
from urllib.parse import urlencode, quote_plus
from dataclasses import dataclass
from pathlib import Path

# Load environment variables from .env file
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('job_finder.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class JobListing(BaseModel):
    job_title: str = Field(..., description="Title of the job position")
    company_name: str = Field(..., description="Name of the company offering the job")
    location: str = Field(..., description="Job location, can be remote or physical location")
    job_description: str = Field(..., description="Detailed description of the job requirements and responsibilities")
    required_skills: List[str] = Field(default_factory=list, description="List of skills required for the job")
    application_url: Optional[str] = Field(None, description="Direct URL to apply for the job")
    posted_date: Optional[str] = Field(None, description="When the job was posted")
    salary_range: Optional[str] = Field(None, description="Salary range if provided")
    job_type: Optional[str] = Field(None, description="Full-time, part-time, contract, etc.")
    experience_level: Optional[str] = Field(None, description="Entry level, mid-level, senior, etc.")
    remote_option: Optional[str] = Field(None, description="Remote, hybrid, on-site")
    benefits: Optional[List[str]] = Field(default_factory=list, description="Benefits offered")
    source_url: Optional[str] = Field(None, description="URL where this job was found")
    source_site: Optional[str] = Field(None, description="Name of the job board")
    
    @field_validator('required_skills', mode='before')
    @classmethod
    def parse_skills(cls, v):
        if isinstance(v, str):
            # Try to parse comma-separated or semicolon-separated skills
            skills = re.split(r'[,;]\s*', v)
            return [skill.strip() for skill in skills if skill.strip()]
        return v or []
    
    @field_validator('benefits', mode='before')
    @classmethod
    def parse_benefits(cls, v):
        if isinstance(v, str):
            benefits = re.split(r'[,;]\s*', v)
            return [benefit.strip() for benefit in benefits if benefit.strip()]
        return v or []

class ContactPerson(BaseModel):
    name: str = Field(..., description="Full name of the contact person")
    title: Optional[str] = Field(None, description="Job title of the contact person")
    company: Optional[str] = Field(None, description="Company the contact person works for")
    linkedin_url: Optional[str] = Field(None, description="LinkedIn profile URL")
    github_url: Optional[str] = Field(None, description="GitHub profile URL")
    twitter_url: Optional[str] = Field(None, description="Twitter profile URL")
    email: Optional[str] = Field(None, description="Email address if available")
    connection_path: Optional[str] = Field(None, description="How to connect with this person")
    relevance_score: Optional[float] = Field(None, description="Relevance score (0-1)")
    relevance_reason: Optional[str] = Field(None, description="Why this person might be relevant")
    mutual_connections: Optional[int] = Field(None, description="Number of mutual connections")

@dataclass
class JobBoard:
    name: str
    base_url: str
    search_pattern: str
    needs_stealth: bool = False

class EnhancedJobFinder:
    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        self.session = None
        self.job_boards = self._initialize_job_boards()
        self.user_data_dir = os.path.join(Path.home(), ".crawl4ai", "job_finder_profile")
        os.makedirs(self.user_data_dir, exist_ok=True)
        
    def _initialize_job_boards(self) -> List[JobBoard]:
        """Initialize comprehensive list of job boards with their configurations"""
        return [
            JobBoard(
                name="LinkedIn",
                base_url="https://www.linkedin.com",
                search_pattern="/jobs/search/?keywords={keywords}&location={location}&f_TPR=r86400",
                needs_stealth=True  # LinkedIn has strong anti-bot detection
            ),
            JobBoard(
                name="Indeed",
                base_url="https://www.indeed.com",
                search_pattern="/jobs?q={keywords}&l={location}&fromage=1&sort=date",
                needs_stealth=True
            ),
            JobBoard(
                name="Glassdoor",
                base_url="https://www.glassdoor.com",
                search_pattern="/Job/jobs.htm?sc.keyword={keywords}&locT=C&locId=&locKeyword={location}",
                needs_stealth=True
            ),
            JobBoard(
                name="ZipRecruiter",
                base_url="https://www.ziprecruiter.com",
                search_pattern="/jobs/search?search={keywords}&location={location}&days=1",
                needs_stealth=True
            ),
            JobBoard(
                name="AngelList",
                base_url="https://angel.co",
                search_pattern="/jobs?keywords={keywords}&location={location}",
                needs_stealth=False
            ),
            JobBoard(
                name="Remote.co",
                base_url="https://remote.co",
                search_pattern="/remote-jobs/search/?search_keywords={keywords}",
                needs_stealth=False
            ),
            JobBoard(
                name="SimplyHired",
                base_url="https://www.simplyhired.com",
                search_pattern="/search?q={keywords}&l={location}&fdb=1",
                needs_stealth=True
            ),
            JobBoard(
                name="Monster",
                base_url="https://www.monster.com",
                search_pattern="/jobs/search?q={keywords}&where={location}&tm=1",
                needs_stealth=True
            ),
            JobBoard(
                name="Dice",
                base_url="https://www.dice.com",
                search_pattern="/jobs?q={keywords}&location={location}&filters.postedDate=ONE",
                needs_stealth=True
            )
        ]

    def _get_browser_config(self, needs_stealth: bool = False) -> BrowserConfig:
        """Get optimized browser configuration for different site requirements"""
        if needs_stealth:
            # Enhanced stealth configuration for anti-bot protection
            return BrowserConfig(
                headless=True,
                viewport_width=1920,
                viewport_height=1080,
                java_script_enabled=True,
                use_persistent_context=True,
                user_data_dir=self.user_data_dir,
                user_agent_mode="random",  # Use random user agent rotation
                user_agent_generator_config={
                    "device_type": "desktop",
                    "os_type": "windows"
                },
                # Enhanced headers to mimic real browser
                headers={
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                    "Accept-Language": "en-US,en;q=0.5",
                    "Accept-Encoding": "gzip, deflate, br",
                    "DNT": "1",
                    "Connection": "keep-alive",
                    "Upgrade-Insecure-Requests": "1",
                    "Sec-Fetch-Dest": "document",
                    "Sec-Fetch-Mode": "navigate",
                    "Sec-Fetch-Site": "none",
                    "Sec-Fetch-User": "?1",
                    "Cache-Control": "max-age=0",
                },
                # Additional anti-detection arguments
                extra_args=[
                    "--disable-blink-features=AutomationControlled",
                    "--disable-features=VizDisplayCompositor",
                    "--disable-extensions",
                    "--no-first-run",
                    "--disable-default-apps",
                    "--disable-component-extensions-with-background-pages",
                ]
            )
        else:
            # Standard configuration for less protected sites
            return BrowserConfig(
                headless=True,
                viewport_width=1920,
                viewport_height=1080,
                java_script_enabled=True,
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )

    def _get_crawler_config(self, needs_stealth: bool = False) -> CrawlerRunConfig:
        """Get optimized crawler configuration for different site requirements"""
        if needs_stealth:
            # Enhanced stealth crawler configuration
            return CrawlerRunConfig(
                cache_mode=CacheMode.BYPASS,
                page_timeout=30000,  # Longer timeout for slower loading
                wait_until="networkidle",  # Wait for network to be idle
                magic=True,  # Enable magic mode for anti-bot handling
                simulate_user=True,  # Simulate user behavior
                override_navigator=True,  # Override navigator properties
                remove_overlay_elements=True,  # Remove popups/modals
                scan_full_page=True,  # Scroll to load dynamic content
                scroll_delay=1.0,  # Slower scrolling to appear human
                delay_before_return_html=3.0,  # Wait before extracting content
                wait_for_images=True,  # Wait for images to load
                # Add random delays to mimic human behavior
                mean_delay=2.0,
                max_range=4.0,
                verbose=True
            )
        else:
            # Standard configuration
            return CrawlerRunConfig(
                cache_mode=CacheMode.BYPASS,
                page_timeout=15000,
                wait_until="domcontentloaded",
                delay_before_return_html=2.0,
                verbose=True
            )

    async def search_job_board(self, job_board: JobBoard, keywords: str, location: str = "") -> List[JobListing]:
        """Search a specific job board for job listings with enhanced anti-bot protection"""
        logger.info(f"Searching {job_board.name} for '{keywords}' in '{location}' (stealth: {job_board.needs_stealth})")
        
        # Construct search URL
        search_url = job_board.base_url + job_board.search_pattern.format(
            keywords=quote_plus(keywords),
            location=quote_plus(location)
        )
        
        logger.info(f"Search URL: {search_url}")
        
        jobs = []
        
        # Get appropriate configuration based on site requirements
        browser_config = self._get_browser_config(job_board.needs_stealth)
        crawler_config = self._get_crawler_config(job_board.needs_stealth)
        
        async with AsyncWebCrawler(config=browser_config) as crawler:
            try:
                # Use LLM-based extraction with enhanced configuration
                llm_jobs = await self._extract_with_llm(crawler, search_url, job_board.name, crawler_config)
                if llm_jobs:
                    jobs.extend(llm_jobs)
                    logger.info(f"Found {len(llm_jobs)} jobs from {job_board.name}")
                else:
                    logger.info(f"No jobs found from {job_board.name}")
                
            except Exception as e:
                logger.error(f"Error searching {job_board.name}: {str(e)}")
                
                # For stealth sites, try a fallback approach
                if job_board.needs_stealth:
                    logger.info(f"Attempting fallback method for {job_board.name}")
                    try:
                        fallback_jobs = await self._fallback_stealth_extraction(crawler, search_url, job_board.name, crawler_config)
                        if fallback_jobs:
                            jobs.extend(fallback_jobs)
                            logger.info(f"Fallback found {len(fallback_jobs)} jobs from {job_board.name}")
                    except Exception as fallback_e:
                        logger.error(f"Fallback also failed for {job_board.name}: {str(fallback_e)}")
        
        # Set source information
        for job in jobs:
            job.source_site = job_board.name
            job.source_url = search_url
        
        return jobs

    async def _fallback_stealth_extraction(self, crawler, url: str, site_name: str, crawler_config: CrawlerRunConfig) -> List[JobListing]:
        """Fallback extraction method for heavily protected sites"""
        
        # Enhanced stealth configuration for fallback
        stealth_config = crawler_config.clone(
            # Even more aggressive stealth settings
            page_timeout=45000,
            delay_before_return_html=5.0,
            scan_full_page=True,
            scroll_delay=2.0,
            # Try to wait for specific elements that indicate the page has loaded
            wait_for="css:div,article,section",
            # Additional time for anti-bot checks to complete
            magic=True,
            simulate_user=True,
        )
        
        try:
            result = await crawler.arun(url=url, config=stealth_config)
            
            if result.success and result.markdown:
                # Use a simplified extraction approach for the fallback
                return self._extract_from_markdown(result.markdown, site_name)
            else:
                logger.warning(f"Fallback extraction failed for {site_name}: {result.error_message}")
                return []
                
        except Exception as e:
            logger.error(f"Fallback stealth extraction error for {site_name}: {e}")
            return []

    def _extract_from_markdown(self, markdown_content: str, site_name: str) -> List[JobListing]:
        """Extract job information from markdown content using pattern matching"""
        jobs = []
        
        # Simple pattern-based extraction as fallback
        # Look for job-like patterns in markdown
        lines = markdown_content.split('\n')
        current_job = {}
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            # Look for job titles (often in headers or bold)
            if any(keyword in line.lower() for keyword in ['engineer', 'developer', 'manager', 'analyst', 'specialist']):
                if current_job and current_job.get('job_title'):
                    # Save previous job if we have enough info
                    if current_job.get('company_name'):
                        try:
                            job = JobListing(
                                job_title=current_job['job_title'],
                                company_name=current_job['company_name'],
                                location=current_job.get('location', 'Not specified'),
                                job_description=current_job.get('description', line)
                            )
                            jobs.append(job)
                        except Exception as e:
                            logger.debug(f"Error creating job from markdown: {e}")
                
                # Start new job
                current_job = {'job_title': line}
            
            elif current_job and not current_job.get('company_name'):
                # Next non-empty line might be company
                if line and not line.startswith(('http', 'www', 'apply')):
                    current_job['company_name'] = line
        
        # Don't forget the last job
        if current_job and current_job.get('job_title') and current_job.get('company_name'):
            try:
                job = JobListing(
                    job_title=current_job['job_title'],
                    company_name=current_job['company_name'],
                    location=current_job.get('location', 'Not specified'),
                    job_description=current_job.get('description', 'Job description not available')
                )
                jobs.append(job)
            except Exception as e:
                logger.debug(f"Error creating final job from markdown: {e}")
        
        logger.info(f"Extracted {len(jobs)} jobs from markdown for {site_name}")
        return jobs

    async def _extract_with_llm(self, crawler, url: str, site_name: str, crawler_config: CrawlerRunConfig) -> List[JobListing]:
        """Extract jobs using LLM-based extraction with enhanced anti-bot handling"""
        extraction_strategy = LLMExtractionStrategy(
            llm_config=LLMConfig(
                provider="openai/gpt-4o-mini",
                api_token=self.api_key
            ),
            schema=JobListing.model_json_schema(),
            extraction_type="schema",
            instruction=f"""
            Extract ALL job listings from this {site_name} page. Look for actual job postings, not navigation links or categories.
            
            For each real job listing, extract:
            
            REQUIRED FIELDS:
            - job_title: The exact job title (e.g., "Software Engineer", "Data Scientist")
            - company_name: The company name posting the job
            - location: Job location (city, state, or "Remote")
            - job_description: Brief description of the role and responsibilities
            
            OPTIONAL FIELDS (if available):
            - required_skills: Array of skills like ["Python", "React", "AWS"]
            - application_url: Direct apply link
            - posted_date: When posted (e.g., "2 days ago")
            - salary_range: Salary information
            - job_type: "Full-time", "Part-time", "Contract", etc.
            - experience_level: "Entry", "Mid", "Senior", etc.
            - remote_option: "Remote", "Hybrid", "On-site"
            - benefits: Array of benefits

            IMPORTANT:
            - Only extract actual job postings, skip ads and navigation
            - If information isn't available, leave it null/empty
            - Return valid JSON array of job objects
            - Focus on real job opportunities only
            - Extract at least the job title and company name for each listing
            """
        )
        
        # Set the extraction strategy in the crawler config
        enhanced_config = crawler_config.clone(extraction_strategy=extraction_strategy)
        
        try:
            result = await crawler.arun(url=url, config=enhanced_config)
            
            if result.success and result.extracted_content:
                # Add debugging for extracted content
                logger.debug(f"Raw extracted content from {site_name}: {result.extracted_content[:500]}...")
                
                # Check if extracted_content is None or empty
                if not result.extracted_content or not result.extracted_content.strip():
                    logger.warning(f"Empty extracted content from {site_name}")
                    return []
                
                try:
                    jobs_data = json.loads(result.extracted_content)
                    jobs = []
                    
                    if isinstance(jobs_data, list):
                        for job_data in jobs_data:
                            if self._is_valid_job_data(job_data):
                                try:
                                    # Handle missing location field specifically
                                    if job_data.get('location') is None:
                                        job_data['location'] = "Not specified"
                                    
                                    job = JobListing(**job_data)
                                    jobs.append(job)
                                except Exception as e:
                                    logger.warning(f"Error creating JobListing from {site_name}: {e}")
                                    logger.debug(f"Problematic job data: {job_data}")
                                    continue
                    elif isinstance(jobs_data, dict):
                        # Sometimes the LLM returns a single job as an object
                        if self._is_valid_job_data(jobs_data):
                            try:
                                # Handle missing location field specifically
                                if jobs_data.get('location') is None:
                                    jobs_data['location'] = "Not specified"
                                
                                job = JobListing(**jobs_data)
                                jobs.append(job)
                            except Exception as e:
                                logger.warning(f"Error creating JobListing from {site_name}: {e}")
                                logger.debug(f"Problematic job data: {jobs_data}")
                    
                    return jobs
                    
                except json.JSONDecodeError as e:
                    logger.warning(f"JSON decode error for {site_name}: {e}")
                    logger.debug(f"Raw content that failed to parse: {result.extracted_content[:1000]}...")
                    # Try to extract basic info from raw content
                    return self._fallback_extraction(result.extracted_content, site_name)
            else:
                logger.warning(f"No content extracted from {site_name}. Success: {result.success}, Error: {result.error_message}")
                return []
                
        except Exception as e:
            logger.error(f"LLM extraction error for {site_name}: {e}")
            logger.debug(f"Full error details: {e.__class__.__name__}: {str(e)}")
            return []

    def _fallback_extraction(self, content: str, site_name: str) -> List[JobListing]:
        """Fallback extraction when JSON parsing fails"""
        try:
            # Try to find job-like patterns in the content
            jobs = []
            
            # Look for common job title patterns
            job_patterns = [
                r'software engineer',
                r'data scientist',
                r'product manager',
                r'developer',
                r'engineer',
                r'manager',
                r'analyst'
            ]
            
            # This is a very basic fallback - in a real implementation,
            # you'd want more sophisticated parsing
            for pattern in job_patterns:
                if re.search(pattern, content, re.IGNORECASE):
                    job = JobListing(
                        job_title=f"Job found on {site_name}",
                        company_name="Company name not extracted",
                        location="Location not specified",
                        job_description=content[:200] + "..." if len(content) > 200 else content
                    )
                    jobs.append(job)
                    break  # Only create one fallback job per site
            
            return jobs
        except Exception as e:
            logger.error(f"Fallback extraction failed: {e}")
            return []

    def _is_valid_job_data(self, job_data: Dict) -> bool:
        """Validate if job data is meaningful"""
        if not isinstance(job_data, dict):
            return False
        
        # Must have title and company
        title = job_data.get("job_title", "").strip()
        company = job_data.get("company_name", "").strip()
        
        if not title or not company:
            return False
        
        # Filter out generic/spam entries
        spam_indicators = [
            "similar jobs", "related jobs", "more jobs", "view all",
            "job alert", "email alert", "save search", "job search",
            "sign up", "create account", "login"
        ]
        
        title_lower = title.lower()
        return not any(indicator in title_lower for indicator in spam_indicators)

    async def search_all_job_boards(self, keywords: str, location: str = "", max_parallel: int = 2) -> List[JobListing]:
        """Search all job boards in parallel with reduced concurrency for stealth"""
        logger.info(f"Starting comprehensive job search for '{keywords}' in '{location}'")
        
        all_jobs = []
        
        # Separate stealth-required and regular sites
        stealth_boards = [board for board in self.job_boards if board.needs_stealth]
        regular_boards = [board for board in self.job_boards if not board.needs_stealth]
        
        # Process stealth sites with more care (lower concurrency, longer delays)
        if stealth_boards:
            logger.info(f"Processing {len(stealth_boards)} stealth-required sites with enhanced protection")
            for board in stealth_boards:
                try:
                    jobs = await self.search_job_board(board, keywords, location)
                    all_jobs.extend(jobs)
                    logger.info(f"Found {len(jobs)} jobs from {board.name}")
                    
                    # Longer delay between stealth sites to avoid detection
                    await asyncio.sleep(5)
                    
                except Exception as e:
                    logger.error(f"Error with stealth site {board.name}: {e}")
        
        # Process regular sites in parallel
        if regular_boards:
            logger.info(f"Processing {len(regular_boards)} regular sites in parallel")
            for i in range(0, len(regular_boards), max_parallel):
                batch = regular_boards[i:i + max_parallel]
                
                tasks = [
                    self.search_job_board(job_board, keywords, location)
                    for job_board in batch
                ]
                
                batch_results = await asyncio.gather(*tasks, return_exceptions=True)
                
                for idx, result in enumerate(batch_results):
                    if isinstance(result, Exception):
                        logger.error(f"Error with {batch[idx].name}: {result}")
                    elif isinstance(result, list):
                        all_jobs.extend(result)
                        logger.info(f"Found {len(result)} jobs from {batch[idx].name}")
                
                # Rate limiting between batches
                if i + max_parallel < len(regular_boards):
                    await asyncio.sleep(2)
        
        # Deduplicate jobs
        unique_jobs = self._deduplicate_jobs(all_jobs)
        logger.info(f"Total unique jobs found: {len(unique_jobs)}")
        
        return unique_jobs

    def _deduplicate_jobs(self, jobs: List[JobListing]) -> List[JobListing]:
        """Remove duplicate job listings"""
        seen = set()
        unique_jobs = []
        
        for job in jobs:
            # Create a key based on title, company, and location
            key = (
                job.job_title.lower().strip(),
                job.company_name.lower().strip(),
                job.location.lower().strip() if job.location else ""
            )
            
            if key not in seen:
                seen.add(key)
                unique_jobs.append(job)
        
        return unique_jobs

    def _resolve_url(self, url: str, base_url: str) -> str:
        """Resolve relative URLs to absolute URLs"""
        if url.startswith('http'):
            return url
        elif url.startswith('//'):
            return 'https:' + url
        elif url.startswith('/'):
            return base_url.rstrip('/') + url
        else:
            return base_url.rstrip('/') + '/' + url

    async def find_connections_enhanced(self, job: JobListing) -> List[ContactPerson]:
        """Find professional connections using LinkedIn search with enhanced stealth"""
        logger.info(f"Finding connections for {job.job_title} at {job.company_name}")
        
        connections = []
        
        # Search LinkedIn for company employees using stealth mode
        linkedin_connections = await self._search_linkedin_connections(job)
        connections.extend(linkedin_connections)
        
        # Score and rank connections
        scored_connections = self._score_connections(connections, job)
        
        # Return top connections
        return sorted(scored_connections, key=lambda x: x.relevance_score or 0, reverse=True)[:20]

    async def _search_linkedin_connections(self, job: JobListing) -> List[ContactPerson]:
        """Search LinkedIn for company employees with enhanced stealth"""
        search_terms = [
            f"{job.company_name} {job.job_title}",
            f"{job.company_name} engineer",
            f"{job.company_name} manager"
        ]
        
        connections = []
        
        # Use stealth configuration for LinkedIn
        browser_config = self._get_browser_config(needs_stealth=True)
        crawler_config = self._get_crawler_config(needs_stealth=True)
        
        async with AsyncWebCrawler(config=browser_config) as crawler:
            for search_term in search_terms[:2]:  # Limit to avoid rate limiting
                search_url = f"https://www.linkedin.com/search/results/people/?keywords={quote_plus(search_term)}"
                
                extraction_strategy = LLMExtractionStrategy(
                    llm_config=LLMConfig(
                        provider="openai/gpt-4o-mini",
                        api_token=self.api_key
                    ),
                    schema=ContactPerson.model_json_schema(),
                    extraction_type="schema",
                    instruction=f"""
                    Extract information about people who work at {job.company_name} from this LinkedIn search page.
                    For each person, extract:
                    - name: Full name
                    - title: Current job title  
                    - company: Company name
                    - linkedin_url: Their LinkedIn profile URL
                    - relevance_reason: Why they might be relevant for a {job.job_title} position
                    
                    Focus on people who work at {job.company_name} and could help with job applications.
                    Return an array of person objects.
                    """
                )
                
                config = crawler_config.clone(extraction_strategy=extraction_strategy)
                
                try:
                    result = await crawler.arun(url=search_url, config=config)
                    
                    if result.success and result.extracted_content:
                        try:
                            people_data = json.loads(result.extracted_content)
                            for person_data in people_data:
                                if person_data.get("name"):
                                    connection = ContactPerson(**person_data)
                                    connections.append(connection)
                        except json.JSONDecodeError:
                            logger.warning(f"Error parsing LinkedIn connections data")
                    
                    await asyncio.sleep(5)  # Longer delay for LinkedIn
                    
                except Exception as e:
                    logger.error(f"Error searching LinkedIn connections: {e}")
        
        return connections

    def _score_connections(self, connections: List[ContactPerson], job: JobListing) -> List[ContactPerson]:
        """Score and rank connections based on relevance"""
        for connection in connections:
            score = 0.0
            
            # Score based on title relevance
            if connection.title:
                title_lower = connection.title.lower()
                job_title_lower = job.job_title.lower()
                
                # Exact title match
                if job_title_lower in title_lower:
                    score += 0.5
                
                # Similar role keywords
                keywords = ["engineer", "developer", "manager", "director", "lead", "senior"]
                for keyword in keywords:
                    if keyword in title_lower and keyword in job_title_lower:
                        score += 0.2
            
            # Score based on company match
            if connection.company and job.company_name.lower() in connection.company.lower():
                score += 0.3
            
            connection.relevance_score = min(score, 1.0)
        
        return connections

    def save_results(self, jobs: List[JobListing], connections: List[ContactPerson] = None, filename: str = None) -> str:
        """Save search results to file"""
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"output/job_search_results_{timestamp}.json"
        
        # Ensure output directory exists
        os.makedirs("output", exist_ok=True)
        
        results = {
            "search_metadata": {
                "timestamp": datetime.now().isoformat(),
                "total_jobs": len(jobs),
                "total_connections": len(connections) if connections else 0,
                "job_boards_searched": [board.name for board in self.job_boards],
                "stealth_enabled": True
            },
            "jobs": [job.dict() for job in jobs],
            "connections": [conn.dict() for conn in connections] if connections else []
        }
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Saved {len(jobs)} jobs and {len(connections) if connections else 0} connections to {filename}")
        return filename

    def print_job_summary(self, jobs: List[JobListing]):
        """Print a detailed summary of jobs found"""
        if not jobs:
            print("No jobs found.")
            return
        
        print(f"\n{'='*80}")
        print(f"FOUND {len(jobs)} JOBS (Enhanced Anti-Bot Protection)")
        print(f"{'='*80}")
        
        # Group by source
        by_source = {}
        for job in jobs:
            source = job.source_site or "Unknown"
            by_source.setdefault(source, []).append(job)
        
        print(f"\nJobs by source:")
        for source, source_jobs in by_source.items():
            stealth_indicator = " (🛡️ Stealth Mode)" if any(board.name == source and board.needs_stealth for board in self.job_boards) else ""
            print(f"  {source}: {len(source_jobs)} jobs{stealth_indicator}")
        
        print(f"\n{'-'*80}")
        
        for i, job in enumerate(jobs, 1):
            print(f"\n{i}. {job.job_title}")
            print(f"   Company: {job.company_name}")
            print(f"   Location: {job.location}")
            print(f"   Source: {job.source_site}")
            
            if job.salary_range:
                print(f"   Salary: {job.salary_range}")
            
            if job.job_type:
                print(f"   Type: {job.job_type}")
            
            if job.experience_level:
                print(f"   Level: {job.experience_level}")
            
            if job.remote_option:
                print(f"   Remote: {job.remote_option}")
            
            if job.required_skills:
                skills = ", ".join(job.required_skills[:5])  # Show first 5 skills
                if len(job.required_skills) > 5:
                    skills += f" (+{len(job.required_skills) - 5} more)"
                print(f"   Skills: {skills}")
            
            if job.application_url:
                print(f"   Apply: {job.application_url}")
            
            if job.posted_date:
                print(f"   Posted: {job.posted_date}")
            
            # Show first 200 chars of description
            if job.job_description and len(job.job_description) > 10:
                desc = job.job_description[:200]
                if len(job.job_description) > 200:
                    desc += "..."
                print(f"   Description: {desc}")
            
            print(f"{'-'*80}")

async def main():
    """Enhanced main function with comprehensive job search and anti-bot protection"""
    print("🚀 Enhanced Job Finder with Anti-Bot Protection")
    print("=" * 60)
    
    # Get API key
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        api_key = input("Enter your OpenAI API key: ")
    
    if not api_key:
        print("❌ OpenAI API key is required for job extraction.")
        return
    
    # Initialize job finder
    job_finder = EnhancedJobFinder(api_key)
    
    # Get search parameters
    print("\n📋 Search Parameters")
    job_query = input("Job title/keywords (e.g., 'software engineer', 'data scientist'): ")
    location = input("Location (optional - city, state, or 'remote'): ").strip()
    
    if not location:
        location = ""
    
    print(f"\n🔍 Searching for '{job_query}' jobs in '{location or 'any location'}'...")
    print("🛡️ Using enhanced anti-bot protection for protected sites (LinkedIn, Indeed, etc.)")
    print("This will search multiple job boards and may take several minutes.\n")
    
    start_time = time.time()
    
    try:
        # Search all job boards with enhanced protection
        jobs = await job_finder.search_all_job_boards(job_query, location)
        
        search_time = time.time() - start_time
        print(f"\n⏱️  Search completed in {search_time:.2f} seconds")
        
        if not jobs:
            print("❌ No jobs found. Try different keywords or location.")
            print("💡 If sites are being blocked, try running again later as the stealth features need time to build reputation.")
            return
        
        # Print summary
        job_finder.print_job_summary(jobs)
        
        # Save results
        filename = job_finder.save_results(jobs)
        print(f"\n💾 Results saved to: {filename}")
        
        # Ask about connection finding
        if jobs:
            print(f"\n🤝 Connection Finding")
            find_connections = input("Find professional connections for a specific job? (y/n): ").lower() == 'y'
            
            if find_connections:
                try:
                    job_num = int(input(f"Enter job number (1-{len(jobs)}): ")) - 1
                    
                    if 0 <= job_num < len(jobs):
                        selected_job = jobs[job_num]
                        print(f"\n🔍 Finding connections for:")
                        print(f"   {selected_job.job_title} at {selected_job.company_name}")
                        print("🛡️ Using stealth mode for LinkedIn search...")
                        
                        connections = await job_finder.find_connections_enhanced(selected_job)
                        
                        if connections:
                            print(f"\n👥 Found {len(connections)} potential connections:")
                            print("-" * 60)
                            
                            for i, person in enumerate(connections[:10], 1):  # Show top 10
                                print(f"{i}. {person.name}")
                                if person.title:
                                    print(f"   Title: {person.title}")
                                if person.company:
                                    print(f"   Company: {person.company}")
                                if person.linkedin_url:
                                    print(f"   LinkedIn: {person.linkedin_url}")
                                if person.relevance_reason:
                                    print(f"   Why relevant: {person.relevance_reason}")
                                if person.relevance_score:
                                    print(f"   Relevance score: {person.relevance_score:.2f}")
                                print("-" * 60)
                            
                            # Save updated results with connections
                            job_finder.save_results(jobs, connections, filename)
                            
                        else:
                            print("❌ No connections found for this job.")
                            print("💡 This might be due to LinkedIn's anti-bot protection. Try again later.")
                    else:
                        print("❌ Invalid job number.")
                        
                except ValueError:
                    print("❌ Please enter a valid number.")
        
        print("\n✅ Job search completed successfully!")
        print("🛡️ Enhanced anti-bot protection helped access protected job sites.")
        
    except Exception as e:
        logger.error(f"Error in main job search: {e}")
        print(f"❌ An error occurred: {e}")
        print("💡 If you're getting blocked, the stealth features are working to build a better reputation for next time.")

if __name__ == "__main__":
    asyncio.run(main()) 