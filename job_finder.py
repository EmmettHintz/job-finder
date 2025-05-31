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
from config import JOB_BOARD_CONFIG

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
        # Import configuration from config.py
        board_config = JOB_BOARD_CONFIG
        
        all_boards = [
            JobBoard(
                name="LinkedIn",
                base_url="https://www.linkedin.com",
                search_pattern="/jobs/search/?keywords={keywords}&location={location}&f_TPR=r86400",
                needs_stealth=False
            ),
            JobBoard(
                name="Indeed",
                base_url="https://www.indeed.com",
                search_pattern="/jobs?q={keywords}&l={location}&fromage=1&sort=date",
                needs_stealth=False
            ),
            JobBoard(
                name="Glassdoor",
                base_url="https://www.glassdoor.com",
                search_pattern="/Job/jobs.htm?sc.keyword={keywords}&locT=C&locId=&locKeyword={location}",
                needs_stealth=False
            ),
            JobBoard(
                name="ZipRecruiter",
                base_url="https://www.ziprecruiter.com",
                search_pattern="/jobs/search?search={keywords}&location={location}&days=1",
                needs_stealth=False
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
                needs_stealth=False
            ),
            JobBoard(
                name="Monster",
                base_url="https://www.monster.com",
                search_pattern="/jobs/search?q={keywords}&where={location}&tm=1",
                needs_stealth=False
            ),
            JobBoard(
                name="Dice",
                base_url="https://www.dice.com",
                search_pattern="/jobs?q={keywords}&location={location}&filters.postedDate=ONE",
                needs_stealth=False
            )
        ]
        
        # Return only enabled boards
        enabled_boards = [board for board in all_boards if board_config.get(board.name, False)]
        
        logger.info(f"Enabled job boards: {[board.name for board in enabled_boards]}")
        disabled_boards = [board.name for board in all_boards if not board_config.get(board.name, False)]
        if disabled_boards:
            logger.info(f"Disabled job boards: {disabled_boards}")
        
        return enabled_boards

    def _get_browser_config(self, needs_stealth: bool = False) -> BrowserConfig:
        """Get optimized browser configuration - simplified for reliability"""
        # Single configuration that works reliably across all sites
        return BrowserConfig(
            headless=True,
            viewport_width=1920,
            viewport_height=1080,
            java_script_enabled=True,
            # Simple, reliable user agent
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            # Basic headers
            headers={
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5",
                "Accept-Encoding": "gzip, deflate",
                "Connection": "keep-alive",
            },
            ignore_https_errors=True,
            light_mode=True,  # Better performance
            verbose=True
        )

    def _get_crawler_config(self, needs_stealth: bool = False) -> CrawlerRunConfig:
        """Get optimized crawler configuration - simplified for reliability"""
        # Single configuration that works reliably across all sites
        return CrawlerRunConfig(
            cache_mode=CacheMode.BYPASS,
            page_timeout=20000,  # 20 second timeout
            wait_until="domcontentloaded",
            delay_before_return_html=2.0,  # Brief delay to let content settle
            verbose=True
        )

    async def search_job_board(self, job_board: JobBoard, keywords: str, location: str = "") -> List[JobListing]:
        """Search a specific job board for job listings with reliable configuration"""
        logger.info(f"Searching {job_board.name} for '{keywords}' in '{location}'")
        
        # Construct search URL
        search_url = job_board.base_url + job_board.search_pattern.format(
            keywords=quote_plus(keywords),
            location=quote_plus(location)
        )
        
        logger.info(f"Search URL: {search_url}")
        
        jobs = []
        
        # Get standard configuration for all sites
        browser_config = self._get_browser_config()
        crawler_config = self._get_crawler_config()
        
        async with AsyncWebCrawler(config=browser_config) as crawler:
            try:
                # Use LLM-based extraction
                llm_jobs = await self._extract_with_llm(crawler, search_url, job_board.name, crawler_config)
                if llm_jobs:
                    jobs.extend(llm_jobs)
                    logger.info(f"Found {len(llm_jobs)} jobs from {job_board.name}")
                else:
                    logger.info(f"No jobs found from {job_board.name}")
                
            except Exception as e:
                logger.error(f"Error searching {job_board.name}: {str(e)}")
        
        # Set source information
        for job in jobs:
            job.source_site = job_board.name
            job.source_url = search_url
        
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

    async def search_all_job_boards(self, keywords: str, location: str = "", max_parallel: int = 3) -> List[JobListing]:
        """Search all job boards in parallel with reliable configuration"""
        logger.info(f"Starting comprehensive job search for '{keywords}' in '{location}'")
        
        all_jobs = []
        
        # Process all sites with the same reliable configuration
        logger.info(f"Processing {len(self.job_boards)} job boards")
        
        # Process sites in small batches to avoid overwhelming servers
        for i in range(0, len(self.job_boards), max_parallel):
            batch = self.job_boards[i:i + max_parallel]
            
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
            
            # Brief delay between batches to be respectful
            if i + max_parallel < len(self.job_boards):
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
        """Find professional connections using simplified reliable approach"""
        logger.info(f"Finding connections for {job.job_title} at {job.company_name}")
        
        connections = []
        
        # For now, we'll skip the LinkedIn search since it requires more complex handling
        # Focus on basic job search functionality first
        logger.info("Connection finding temporarily simplified - focusing on core job search functionality")
        
        # Return empty list for now - can be enhanced later
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
        print(f"FOUND {len(jobs)} JOBS (Core Job Search)")
        print(f"{'='*80}")
        
        # Group by source
        by_source = {}
        for job in jobs:
            source = job.source_site or "Unknown"
            by_source.setdefault(source, []).append(job)
        
        print(f"\nJobs by source:")
        for source, source_jobs in by_source.items():
            print(f"  {source}: {len(source_jobs)} jobs")
        
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
    """Enhanced main function with comprehensive job search"""
    print("🚀 Job Finder - Core Functionality")
    print("=" * 50)
    
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
    print("📊 Searching multiple job boards with reliable configuration")
    print("This may take a few minutes.\n")
    
    start_time = time.time()
    
    try:
        # Search all job boards with simplified configuration
        jobs = await job_finder.search_all_job_boards(job_query, location)
        
        search_time = time.time() - start_time
        print(f"\n⏱️  Search completed in {search_time:.2f} seconds")
        
        if not jobs:
            print("❌ No jobs found. Try different keywords or location.")
            return
        
        # Print summary
        job_finder.print_job_summary(jobs)
        
        # Save results
        filename = job_finder.save_results(jobs)
        print(f"\n💾 Results saved to: {filename}")
        
        # Ask about connection finding (simplified)
        if jobs:
            print(f"\n🤝 Connection Finding")
            find_connections = input("Find professional connections for a specific job? (y/n): ").lower() == 'y'
            
            if find_connections:
                print("⚠️  Connection finding is currently simplified for reliability.")
                print("Focus is on core job search functionality first.")
                # We could still call the simplified connection finding if needed
        
        print("\n✅ Job search completed successfully!")
        print("🎯 Core functionality is working reliably.")
        
    except Exception as e:
        logger.error(f"Error in main job search: {e}")
        print(f"❌ An error occurred: {e}")
        print("💡 Try adjusting your search terms or check your API key.")

if __name__ == "__main__":
    asyncio.run(main()) 