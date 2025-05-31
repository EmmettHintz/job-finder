#!/usr/bin/env python3
"""
Example usage of the Enhanced Job Finder
This script demonstrates how to use the job finder programmatically
"""

import asyncio
import os
from job_finder import EnhancedJobFinder

async def simple_job_search():
    """Simple example of searching for jobs"""
    print("🔍 Simple Job Search Example")
    print("=" * 40)
    
    # Initialize job finder
    finder = EnhancedJobFinder()
    
    # Search for software engineer jobs in San Francisco
    jobs = await finder.search_all_job_boards(
        keywords="software engineer",
        location="San Francisco, CA"
    )
    
    print(f"Found {len(jobs)} jobs!")
    
    # Show first 3 jobs
    for i, job in enumerate(jobs[:3], 1):
        print(f"\n{i}. {job.job_title} at {job.company_name}")
        print(f"   Location: {job.location}")
        print(f"   Source: {job.source_site}")
        if job.salary_range:
            print(f"   Salary: {job.salary_range}")

async def comprehensive_search_with_connections():
    """Example of comprehensive search with connection finding"""
    print("\n🎯 Comprehensive Search with Connections")
    print("=" * 45)
    
    # Initialize job finder
    finder = EnhancedJobFinder()
    
    # Search for data scientist jobs (remote)
    jobs = await finder.search_all_job_boards(
        keywords="data scientist",
        location="remote"
    )
    
    if jobs:
        print(f"Found {len(jobs)} data scientist jobs!")
        
        # Pick the first job for connection finding
        target_job = jobs[0]
        print(f"\nFinding connections for: {target_job.job_title} at {target_job.company_name}")
        
        # Find connections
        connections = await finder.find_connections_enhanced(target_job)
        
        if connections:
            print(f"Found {len(connections)} potential connections:")
            for i, conn in enumerate(connections[:3], 1):
                print(f"{i}. {conn.name} - {conn.title}")
                if conn.relevance_score:
                    print(f"   Relevance: {conn.relevance_score:.2f}")
        
        # Save results
        filename = finder.save_results(jobs, connections)
        print(f"\nResults saved to: {filename}")

async def tech_job_search():
    """Example focused on tech jobs"""
    print("\n💻 Tech Job Search Example")
    print("=" * 30)
    
    finder = EnhancedJobFinder()
    
    # Search for Python developer jobs
    python_jobs = await finder.search_all_job_boards(
        keywords="Python developer",
        location="New York, NY"
    )
    
    # Filter jobs with specific skills
    filtered_jobs = [
        job for job in python_jobs 
        if any(skill.lower() in ['python', 'django', 'flask', 'fastapi'] 
               for skill in job.required_skills)
    ]
    
    print(f"Found {len(python_jobs)} Python jobs")
    print(f"Filtered to {len(filtered_jobs)} jobs with specific frameworks")
    
    # Show jobs with salaries
    salary_jobs = [job for job in filtered_jobs if job.salary_range]
    print(f"{len(salary_jobs)} jobs include salary information")
    
    # Show top paying jobs
    if salary_jobs:
        print("\nJobs with salary information:")
        for job in salary_jobs[:3]:
            print(f"- {job.job_title} at {job.company_name}: {job.salary_range}")

async def startup_job_search():
    """Example focused on startup jobs"""
    print("\n🚀 Startup Job Search Example")
    print("=" * 32)
    
    finder = EnhancedJobFinder()
    
    # Search for startup jobs
    startup_jobs = await finder.search_all_job_boards(
        keywords="startup engineer",
        location="San Francisco, CA"
    )
    
    # Filter for jobs from AngelList or with startup keywords
    startup_filtered = [
        job for job in startup_jobs
        if (job.source_site == "AngelList" or 
            any(word in job.job_description.lower() 
                for word in ['startup', 'early stage', 'equity', 'stock options']))
    ]
    
    print(f"Found {len(startup_filtered)} startup-related jobs")
    
    # Show jobs with equity/benefits
    equity_jobs = [
        job for job in startup_filtered
        if job.benefits and any('stock' in benefit.lower() or 'equity' in benefit.lower() 
                               for benefit in job.benefits)
    ]
    
    print(f"{len(equity_jobs)} jobs mention equity/stock options")

async def remote_job_search():
    """Example focused on remote jobs"""
    print("\n🏠 Remote Job Search Example")
    print("=" * 28)
    
    finder = EnhancedJobFinder()
    
    # Search specifically for remote jobs
    remote_jobs = await finder.search_all_job_boards(
        keywords="remote software engineer",
        location="remote"
    )
    
    # Filter for truly remote positions
    fully_remote = [
        job for job in remote_jobs
        if (job.remote_option and 'remote' in job.remote_option.lower()) or
           (job.location and 'remote' in job.location.lower())
    ]
    
    print(f"Found {len(fully_remote)} fully remote jobs")
    
    # Group by time zones or regions if location info available
    us_remote = [
        job for job in fully_remote
        if job.location and any(state in job.location 
                               for state in ['CA', 'NY', 'TX', 'FL', 'US', 'United States'])
    ]
    
    print(f"{len(us_remote)} are US-based remote positions")

def show_job_board_coverage():
    """Show which job boards are being searched"""
    print("\n📊 Job Board Coverage")
    print("=" * 22)
    
    finder = EnhancedJobFinder()
    
    print("Searching the following job boards:")
    for i, board in enumerate(finder.job_boards, 1):
        print(f"{i:2d}. {board.name:<15} - {board.base_url}")
    
    print(f"\nTotal: {len(finder.job_boards)} job boards")

async def main():
    """Run all examples"""
    print("🚀 Enhanced Job Finder - Usage Examples")
    print("=" * 50)
    
    # Show job board coverage
    show_job_board_coverage()
    
    # Run examples (comment out any you don't want to run)
    try:
        await simple_job_search()
        # await comprehensive_search_with_connections()  # Requires API key
        # await tech_job_search()
        # await startup_job_search() 
        # await remote_job_search()
        
        print("\n✅ Examples completed successfully!")
        print("\nTo run the full interactive version:")
        print("python job_finder.py")
        
    except Exception as e:
        print(f"\n❌ Example failed: {e}")
        print("Make sure you have:")
        print("1. OpenAI API key set in .env file")
        print("2. Internet connection")
        print("3. All dependencies installed")

if __name__ == "__main__":
    asyncio.run(main()) 