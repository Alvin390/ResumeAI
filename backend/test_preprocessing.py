#!/usr/bin/env python3
"""
Test script for CV preprocessing pipeline edge cases.
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '.'))

from api.ai import (
    _create_cv_preprocessing_pipeline,
    _detect_cv_format,
    extract_cv_content_with_caching,
    _extract_structured_cv_content,
    _calculate_skills_job_match,
    _score_experience_relevance
)

def test_pdf_table_format():
    """Test PDF with table artifacts."""
    pdf_cv = """
John    Doe                     |    Software Engineer
Email:  john.doe@email.com      |    Phone: (555) 123-4567
                                |
EXPERIENCE                      |
                                |
Senior Developer    |    2020-2024    |    TechCorp Inc
• Led team of 5 developers             |
• Improved system performance by 40%   |
                                       |
SKILLS                                 |
Python    |    JavaScript    |    AWS  |
"""
    
    result = _create_cv_preprocessing_pipeline(pdf_cv, "pdf_with_tables")
    print("=== PDF Table Format Test ===")
    print(f"Detected format: {result['format_info']['detected_format']}")
    print(f"Processing steps: {result['preprocessing_steps']}")
    print(f"Quality score: {result['validation_results']['quality_score']:.2f}")
    print(f"Processed text preview: {result['processed_text'][:200]}...")
    print()

def test_docx_formatting():
    """Test DOCX with special characters."""
    docx_cv = """
Jane Smith
jane.smith@email.com • (555) 987-6543

PROFESSIONAL EXPERIENCE

Marketing Manager – ABC Company – 2019–2023
• Increased brand awareness by 50%
• Managed campaigns with $2M budget
• Led cross-functional teams

SKILLS
• Digital Marketing
• Data Analytics
• Project Management
"""
    
    result = _create_cv_preprocessing_pipeline(docx_cv, "docx_formatted")
    print("=== DOCX Format Test ===")
    print(f"Detected format: {result['format_info']['detected_format']}")
    print(f"Processing steps: {result['preprocessing_steps']}")
    print(f"Quality score: {result['validation_results']['quality_score']:.2f}")
    print()

def test_linkedin_export():
    """Test LinkedIn export format."""
    linkedin_cv = """
LinkedIn Profile Export
John Developer
Connections: 500+

Experience at TechStartup Inc
Software Engineer
Jan 2022 - Present
• Built scalable web applications
• Worked with React, Node.js, MongoDB

Experience at Previous Company
Junior Developer
Jun 2020 - Dec 2021
• Developed REST APIs
• Used Python, Django, PostgreSQL
"""
    
    result = _create_cv_preprocessing_pipeline(linkedin_cv, "unknown")
    print("=== LinkedIn Export Test ===")
    print(f"Detected format: {result['format_info']['detected_format']}")
    print(f"Processing steps: {result['preprocessing_steps']}")
    print()

def test_international_names():
    """Test international name extraction."""
    international_cv = """
José María García-López
jose.garcia@email.com | +34 123 456 789

EXPERIENCIA PROFESIONAL
Ingeniero de Software Senior - TechMadrid - 2020-2024
• Desarrollé aplicaciones web escalables
• Lideré equipo de 8 desarrolladores

HABILIDADES
Python, JavaScript, React, AWS, Docker
"""
    
    result = extract_cv_content_with_caching(international_cv)
    structured = result['structured_content']
    print("=== International Names Test ===")
    print(f"Extracted skills: {[s.get('name') for s in structured.get('skills', [])]}")
    print(f"Experience entries: {len(structured.get('experience', []))}")
    print()

def test_skills_job_matching():
    """Test skills-to-job matching with various formats."""
    cv_skills = [
        {"name": "Python", "type": "programming", "context": "5 years experience"},
        {"name": "JavaScript", "type": "programming", "context": "Frontend development"},
        {"name": "React", "type": "framework", "context": "UI development"},
        {"name": "AWS", "type": "cloud", "context": "Infrastructure management"}
    ]
    
    job_description = """
We are looking for a Senior Full Stack Developer with expertise in:
- Python and Django for backend development
- React.js for frontend applications  
- Cloud platforms (AWS preferred)
- Experience with microservices architecture
- Strong problem-solving skills
"""
    
    requirements = ["Python", "Django", "React", "AWS", "microservices"]
    
    match_result = _calculate_skills_job_match(cv_skills, job_description, requirements)
    print("=== Skills-Job Matching Test ===")
    print(f"Match score: {match_result['match_score']:.1%}")
    print(f"Matched skills: {[s['name'] for s in match_result['matched_skills']]}")
    print(f"Missing skills: {[s['name'] for s in match_result['missing_skills']]}")
    print(f"Skill gaps: {[g['missing_skill'] for g in match_result['skill_gaps']]}")
    print()

def test_experience_relevance():
    """Test experience relevance scoring."""
    experiences = [
        {
            "title": "Senior Software Engineer",
            "company": "TechCorp",
            "duration": "2022-Present",
            "description": ["Led development of microservices", "Managed cloud infrastructure on AWS"]
        },
        {
            "title": "Marketing Coordinator", 
            "company": "RetailCo",
            "duration": "2019-2021",
            "description": ["Managed social media campaigns", "Analyzed customer data"]
        },
        {
            "title": "Full Stack Developer",
            "company": "StartupXYZ",
            "duration": "2021-2022", 
            "description": ["Built React applications", "Developed Python APIs"]
        }
    ]
    
    job_description = """
Senior Full Stack Developer position requiring:
- 5+ years software development experience
- Expertise in Python, React, and cloud platforms
- Experience with microservices architecture
- Leadership and mentoring capabilities
"""
    
    requirements = ["software development", "Python", "React", "cloud", "microservices", "leadership"]
    
    scored = _score_experience_relevance(experiences, job_description, requirements)
    print("=== Experience Relevance Test ===")
    for exp in scored:
        print(f"- {exp['title']} at {exp['company']}: {exp['relevance_score']:.2f}")
        print(f"  Reasons: {', '.join(exp['relevance_reasons'])}")
    print()

def test_edge_cases():
    """Test various edge cases."""
    print("=== Edge Cases Test ===")
    
    # Empty CV
    empty_result = extract_cv_content_with_caching("")
    print(f"Empty CV handling: {empty_result['cached']}")
    
    # Very short CV
    short_cv = "John Doe\njohn@email.com"
    short_result = extract_cv_content_with_caching(short_cv)
    print(f"Short CV quality: {short_result['preprocessing_info']['validation_results']['quality_score']:.2f}")
    
    # Very long CV
    long_cv = "John Doe\n" + "Experience details. " * 1000
    long_result = extract_cv_content_with_caching(long_cv)
    print(f"Long CV processing: {len(long_result['preprocessing_info']['processed_text'])} chars")
    
    # Special characters and encoding
    special_cv = """
Müller Schmidt
müller.schmidt@email.com
Straße 123, München

BERUFSERFAHRUNG
Software-Entwickler – Firma GmbH – 2020–2024
• Entwicklung von Webanwendungen
• Teamführung (5 Mitarbeiter)
"""
    special_result = extract_cv_content_with_caching(special_cv)
    print(f"Special chars handling: {special_result['preprocessing_info']['validation_results']['contact_score']:.2f}")
    print()

def test_caching():
    """Test caching functionality."""
    print("=== Caching Test ===")
    
    test_cv = """
Alice Johnson
alice@email.com | (555) 123-4567

EXPERIENCE
Software Engineer - TechCorp - 2020-2024
• Developed web applications using Python and React
• Improved system performance by 30%

SKILLS
Python, JavaScript, React, SQL, Git
"""
    
    # First call - should process and cache
    result1 = extract_cv_content_with_caching(test_cv)
    print(f"First call cached: {result1['cached']}")
    
    # Second call - should return cached result
    result2 = extract_cv_content_with_caching(test_cv)
    print(f"Second call cached: {result2['cached']}")
    
    # Verify content is identical
    print(f"Results identical: {result1['structured_content'] == result2['structured_content']}")
    print()

if __name__ == "__main__":
    print("Testing CV Preprocessing Pipeline\n")
    print("=" * 50)
    
    test_pdf_table_format()
    test_docx_formatting()
    test_linkedin_export()
    test_international_names()
    test_skills_job_matching()
    test_experience_relevance()
    test_edge_cases()
    test_caching()
    
    print("=" * 50)
    print("All tests completed!")
