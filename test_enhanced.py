#!/usr/bin/env python3
"""
Test script for the Enhanced Job Finder
This script validates key functionality without making actual web requests
"""

import asyncio
import json
from job_finder import EnhancedJobFinder, JobListing, ContactPerson, JobBoard

def test_job_listing_validation():
    """Test JobListing model validation and parsing"""
    print("🧪 Testing JobListing validation...")
    
    # Test valid job listing
    job_data = {
        "job_title": "Senior Software Engineer",
        "company_name": "Tech Corp",
        "location": "San Francisco, CA",
        "job_description": "Build amazing software",
        "required_skills": "Python, React, AWS",  # String that should be parsed
        "salary_range": "$120k - $180k",
        "job_type": "Full-time"
    }
    
    job = JobListing(**job_data)
    print(f"✅ Job created: {job.job_title} at {job.company_name}")
    print(f"   Skills parsed: {job.required_skills}")
    
    # Test with list of skills
    job_data2 = {
        "job_title": "Data Scientist",
        "company_name": "Data Inc",
        "location": "Remote",
        "job_description": "Analyze data and build models",
        "required_skills": ["Python", "SQL", "Machine Learning"],
        "benefits": "Health, 401k, Stock options"  # String that should be parsed
    }
    
    job2 = JobListing(**job_data2)
    print(f"✅ Job 2 created: {job2.job_title} at {job2.company_name}")
    print(f"   Benefits parsed: {job2.benefits}")

def test_contact_person_validation():
    """Test ContactPerson model validation"""
    print("\n🧪 Testing ContactPerson validation...")
    
    contact_data = {
        "name": "John Doe",
        "title": "Engineering Manager",
        "company": "Tech Corp",
        "linkedin_url": "https://linkedin.com/in/johndoe",
        "relevance_score": 0.85
    }
    
    contact = ContactPerson(**contact_data)
    print(f"✅ Contact created: {contact.name} - {contact.title}")
    print(f"   Relevance score: {contact.relevance_score}")

def test_job_board_configuration():
    """Test job board configuration"""
    print("\n🧪 Testing JobBoard configuration...")
    
    finder = EnhancedJobFinder(api_key="test-key")
    print(f"✅ Enhanced Job Finder initialized with {len(finder.job_boards)} job boards:")
    
    for board in finder.job_boards:
        print(f"   - {board.name}: {board.base_url}")

def test_data_validation():
    """Test data validation methods"""
    print("\n🧪 Testing data validation...")
    
    finder = EnhancedJobFinder(api_key="test-key")
    
    # Test valid job data
    valid_job = {
        "job_title": "Software Engineer",
        "company_name": "Great Company",
        "location": "New York"
    }
    
    assert finder._is_valid_job_data(valid_job) == True
    print("✅ Valid job data passed validation")
    
    # Test invalid job data (missing required fields)
    invalid_job = {
        "job_title": "Software Engineer"
        # Missing company_name
    }
    
    assert finder._is_valid_job_data(invalid_job) == False
    print("✅ Invalid job data correctly rejected")
    
    # Test spam job data
    spam_job = {
        "job_title": "similar jobs",
        "company_name": "Spam Corp"
    }
    
    assert finder._is_valid_job_data(spam_job) == False
    print("✅ Spam job data correctly rejected")

def test_url_resolution():
    """Test URL resolution utility"""
    print("\n🧪 Testing URL resolution...")
    
    finder = EnhancedJobFinder(api_key="test-key")
    
    # Test absolute URL (should remain unchanged)
    absolute_url = "https://example.com/job/123"
    resolved = finder._resolve_url(absolute_url, "https://jobboard.com")
    assert resolved == absolute_url
    print("✅ Absolute URL correctly preserved")
    
    # Test relative URL (should be resolved)
    relative_url = "/job/123"
    base_url = "https://jobboard.com"
    resolved = finder._resolve_url(relative_url, base_url)
    assert resolved == "https://jobboard.com/job/123"
    print("✅ Relative URL correctly resolved")
    
    # Test protocol-relative URL
    protocol_relative = "//cdn.example.com/job/123"
    resolved = finder._resolve_url(protocol_relative, base_url)
    assert resolved == "https://cdn.example.com/job/123"
    print("✅ Protocol-relative URL correctly resolved")

def test_deduplication():
    """Test job deduplication"""
    print("\n🧪 Testing job deduplication...")
    
    finder = EnhancedJobFinder(api_key="test-key")
    
    # Create duplicate jobs
    job1 = JobListing(
        job_title="Software Engineer",
        company_name="Tech Corp",
        location="San Francisco",
        job_description="Build software"
    )
    
    job2 = JobListing(
        job_title="Software Engineer",  # Same title
        company_name="Tech Corp",       # Same company
        location="San Francisco",       # Same location
        job_description="Different description"
    )
    
    job3 = JobListing(
        job_title="Data Scientist",    # Different title
        company_name="Tech Corp",
        location="San Francisco",
        job_description="Analyze data"
    )
    
    jobs = [job1, job2, job3]
    unique_jobs = finder._deduplicate_jobs(jobs)
    
    assert len(unique_jobs) == 2  # Should remove one duplicate
    print(f"✅ Deduplication: {len(jobs)} jobs → {len(unique_jobs)} unique jobs")

def test_connection_scoring():
    """Test connection relevance scoring"""
    print("\n🧪 Testing connection scoring...")
    
    finder = EnhancedJobFinder(api_key="test-key")
    
    job = JobListing(
        job_title="Senior Software Engineer",
        company_name="Tech Corp",
        location="San Francisco",
        job_description="Build software"
    )
    
    connections = [
        ContactPerson(
            name="John Doe",
            title="Senior Software Engineer",  # Exact title match
            company="Tech Corp"
        ),
        ContactPerson(
            name="Jane Smith",
            title="Engineering Manager",  # Related title
            company="Tech Corp"
        ),
        ContactPerson(
            name="Bob Wilson",
            title="Marketing Manager",  # Unrelated title
            company="Other Corp"
        )
    ]
    
    scored_connections = finder._score_connections(connections, job)
    
    # Check that exact title match has highest score
    assert scored_connections[0].relevance_score > scored_connections[1].relevance_score
    assert scored_connections[1].relevance_score > scored_connections[2].relevance_score
    
    print("✅ Connection scoring working correctly")
    for conn in scored_connections:
        print(f"   {conn.name}: {conn.relevance_score:.2f}")

async def test_async_functionality():
    """Test async functionality (without making actual requests)"""
    print("\n🧪 Testing async functionality...")
    
    finder = EnhancedJobFinder(api_key="test-key")
    
    # Test that async methods exist and are callable
    assert callable(finder.search_all_job_boards)
    assert callable(finder.find_connections_enhanced)
    print("✅ Async methods are properly defined")

def main():
    """Run all tests"""
    print("🚀 Enhanced Job Finder - Test Suite")
    print("=" * 50)
    
    try:
        test_job_listing_validation()
        test_contact_person_validation()
        test_job_board_configuration()
        test_data_validation()
        test_url_resolution()
        test_deduplication()
        test_connection_scoring()
        asyncio.run(test_async_functionality())
        
        print("\n🎉 All tests passed successfully!")
        print("\n📋 Summary:")
        print("   ✅ JobListing validation working")
        print("   ✅ ContactPerson validation working")
        print("   ✅ Job board configuration loaded")
        print("   ✅ Data validation filtering spam")
        print("   ✅ URL resolution working")
        print("   ✅ Deduplication removing duplicates")
        print("   ✅ Connection scoring ranking relevance")
        print("   ✅ Async functionality ready")
        
        print("\n🚀 Enhanced Job Finder is ready to use!")
        print("   Run: python job_finder.py")
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main() 