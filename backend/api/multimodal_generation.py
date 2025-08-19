"""
Multi-Modal Content Generation System
Generates content with formatting, styling, and multiple output formats.
"""

import os
import json
import re
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from enum import Enum
import logging

logger = logging.getLogger(__name__)

class OutputFormat(Enum):
    """Supported output formats."""
    PLAIN_TEXT = "plain_text"
    MARKDOWN = "markdown"
    HTML = "html"
    LATEX = "latex"
    JSON_STRUCTURED = "json"

class ContentStyle(Enum):
    """Content styling options."""
    PROFESSIONAL = "professional"
    MODERN = "modern"
    CREATIVE = "creative"
    EXECUTIVE = "executive"
    TECHNICAL = "technical"
    ACADEMIC = "academic"

@dataclass
class FormattingOptions:
    """Options for content formatting."""
    output_format: OutputFormat
    style: ContentStyle
    include_headers: bool = True
    include_bullets: bool = True
    include_emphasis: bool = True
    line_spacing: str = "single"  # single, 1.5, double
    font_suggestions: Optional[List[str]] = None
    color_scheme: Optional[str] = None
    
class MultiModalGenerator:
    """Generates content in multiple formats with styling."""
    
    def __init__(self):
        self.style_templates = self._load_style_templates()
        self.format_converters = {
            OutputFormat.PLAIN_TEXT: self._to_plain_text,
            OutputFormat.MARKDOWN: self._to_markdown,
            OutputFormat.HTML: self._to_html,
            OutputFormat.LATEX: self._to_latex,
            OutputFormat.JSON_STRUCTURED: self._to_json
        }
    
    def _load_style_templates(self) -> Dict[ContentStyle, Dict[str, Any]]:
        """Load styling templates for different content styles."""
        return {
            ContentStyle.PROFESSIONAL: {
                "fonts": ["Times New Roman", "Calibri", "Arial"],
                "colors": {"primary": "#000000", "accent": "#2E4057"},
                "spacing": "conservative",
                "tone": "formal",
                "structure": "traditional"
            },
            ContentStyle.MODERN: {
                "fonts": ["Helvetica", "Roboto", "Open Sans"],
                "colors": {"primary": "#333333", "accent": "#007ACC"},
                "spacing": "clean",
                "tone": "contemporary",
                "structure": "streamlined"
            },
            ContentStyle.CREATIVE: {
                "fonts": ["Montserrat", "Lato", "Poppins"],
                "colors": {"primary": "#2C3E50", "accent": "#E74C3C"},
                "spacing": "dynamic",
                "tone": "engaging",
                "structure": "flexible"
            },
            ContentStyle.EXECUTIVE: {
                "fonts": ["Georgia", "Playfair Display", "Merriweather"],
                "colors": {"primary": "#1A1A1A", "accent": "#8B4513"},
                "spacing": "authoritative",
                "tone": "commanding",
                "structure": "hierarchical"
            },
            ContentStyle.TECHNICAL: {
                "fonts": ["Consolas", "Source Code Pro", "Fira Code"],
                "colors": {"primary": "#2F3349", "accent": "#00D2FF"},
                "spacing": "precise",
                "tone": "analytical",
                "structure": "systematic"
            },
            ContentStyle.ACADEMIC: {
                "fonts": ["Computer Modern", "TeX Gyre Termes", "Linux Libertine"],
                "colors": {"primary": "#000000", "accent": "#8B0000"},
                "spacing": "scholarly",
                "tone": "intellectual",
                "structure": "research-oriented"
            }
        }
    
    def generate_multimodal_content(self, 
                                  base_content: str,
                                  content_type: str,
                                  formatting_options: FormattingOptions,
                                  metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Generate content in specified format with styling."""
        
        # Parse and structure the base content
        structured_content = self._parse_content_structure(base_content, content_type)
        
        # Apply styling based on options
        styled_content = self._apply_styling(structured_content, formatting_options)
        
        # Convert to target format
        formatted_content = self.format_converters[formatting_options.output_format](
            styled_content, formatting_options
        )
        
        # Generate metadata
        generation_metadata = {
            "format": formatting_options.output_format.value,
            "style": formatting_options.style.value,
            "generated_at": datetime.now().isoformat(),
            "content_type": content_type,
            "word_count": len(base_content.split()),
            "character_count": len(base_content),
            **(metadata or {})
        }
        
        return {
            "content": formatted_content,
            "metadata": generation_metadata,
            "styling_info": self._get_styling_info(formatting_options),
            "download_suggestions": self._get_download_suggestions(formatting_options)
        }
    
    def _parse_content_structure(self, content: str, content_type: str) -> Dict[str, Any]:
        """Parse content into structured components."""
        structure = {
            "type": content_type,
            "sections": [],
            "contact_info": {},
            "metadata": {}
        }
        
        if content_type == "cover_letter":
            structure.update(self._parse_cover_letter(content))
        elif content_type == "cv":
            structure.update(self._parse_cv(content))
        else:
            structure["sections"] = [{"title": "Content", "content": content}]
        
        return structure
    
    def _parse_cover_letter(self, content: str) -> Dict[str, Any]:
        """Parse cover letter structure."""
        sections = []
        lines = content.split('\n')
        
        current_section = {"title": "Header", "content": ""}
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            # Detect greeting
            if re.match(r'^(Dear|Hello|Hi)', line, re.I):
                if current_section["content"]:
                    sections.append(current_section)
                current_section = {"title": "Greeting", "content": line}
            
            # Detect closing
            elif re.match(r'^(Sincerely|Best regards|Thank you)', line, re.I):
                if current_section["content"]:
                    sections.append(current_section)
                current_section = {"title": "Closing", "content": line}
            
            # Detect signature
            elif re.match(r'^[A-Z][a-z]+ [A-Z][a-z]+$', line):
                if current_section["title"] == "Closing":
                    current_section["content"] += f"\n{line}"
                else:
                    if current_section["content"]:
                        sections.append(current_section)
                    current_section = {"title": "Signature", "content": line}
            
            else:
                if current_section["title"] == "Header" and not current_section["content"]:
                    current_section["content"] = line
                elif current_section["title"] in ["Greeting", "Closing", "Signature"]:
                    current_section["content"] += f"\n{line}"
                else:
                    if current_section["content"]:
                        sections.append(current_section)
                    current_section = {"title": "Body", "content": line}
        
        if current_section["content"]:
            sections.append(current_section)
        
        return {"sections": sections}
    
    def _parse_cv(self, content: str) -> Dict[str, Any]:
        """Parse CV structure."""
        sections = []
        lines = content.split('\n')
        
        current_section = {"title": "Header", "content": ""}
        section_patterns = {
            r'(EXPERIENCE|WORK EXPERIENCE|EMPLOYMENT)': 'Experience',
            r'(EDUCATION|ACADEMIC BACKGROUND)': 'Education',
            r'(SKILLS|TECHNICAL SKILLS|COMPETENCIES)': 'Skills',
            r'(ACHIEVEMENTS|ACCOMPLISHMENTS)': 'Achievements',
            r'(CERTIFICATIONS?|LICENSES?)': 'Certifications',
            r'(PROJECTS?)': 'Projects',
            r'(SUMMARY|PROFILE|OBJECTIVE)': 'Summary'
        }
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Check if line is a section header
            section_found = False
            for pattern, section_name in section_patterns.items():
                if re.match(pattern, line, re.I):
                    if current_section["content"]:
                        sections.append(current_section)
                    current_section = {"title": section_name, "content": ""}
                    section_found = True
                    break
            
            if not section_found:
                if current_section["content"]:
                    current_section["content"] += f"\n{line}"
                else:
                    current_section["content"] = line
        
        if current_section["content"]:
            sections.append(current_section)
        
        return {"sections": sections}
    
    def _apply_styling(self, structured_content: Dict[str, Any], options: FormattingOptions) -> Dict[str, Any]:
        """Apply styling to structured content."""
        style_config = self.style_templates[options.style]
        
        # Apply style-specific modifications
        for section in structured_content["sections"]:
            section["style_class"] = f"{options.style.value}-section"
            section["formatting"] = {
                "font_family": style_config["fonts"][0],
                "color": style_config["colors"]["primary"],
                "spacing": style_config["spacing"]
            }
            
            # Style-specific content modifications
            if options.style == ContentStyle.CREATIVE:
                section["content"] = self._enhance_creative_language(section["content"])
            elif options.style == ContentStyle.TECHNICAL:
                section["content"] = self._enhance_technical_language(section["content"])
            elif options.style == ContentStyle.EXECUTIVE:
                section["content"] = self._enhance_executive_language(section["content"])
        
        structured_content["global_style"] = style_config
        return structured_content
    
    def _enhance_creative_language(self, content: str) -> str:
        """Enhance content with creative language patterns."""
        # Add dynamic action verbs
        creative_replacements = {
            r'\bmanaged\b': 'orchestrated',
            r'\bimproved\b': 'transformed',
            r'\bworked on\b': 'pioneered',
            r'\bhelped\b': 'empowered',
            r'\bcreated\b': 'innovated'
        }
        
        for pattern, replacement in creative_replacements.items():
            content = re.sub(pattern, replacement, content, flags=re.I)
        
        return content
    
    def _enhance_technical_language(self, content: str) -> str:
        """Enhance content with technical precision."""
        # Add technical precision
        technical_enhancements = {
            r'\bbuilt\b': 'architected and implemented',
            r'\bused\b': 'leveraged',
            r'\bworked with\b': 'integrated',
            r'\bimproved\b': 'optimized',
            r'\bfixed\b': 'debugged and resolved'
        }
        
        for pattern, replacement in technical_enhancements.items():
            content = re.sub(pattern, replacement, content, flags=re.I)
        
        return content
    
    def _enhance_executive_language(self, content: str) -> str:
        """Enhance content with executive-level language."""
        # Add executive authority
        executive_enhancements = {
            r'\bmanaged\b': 'directed',
            r'\bworked on\b': 'spearheaded',
            r'\bhelped\b': 'facilitated',
            r'\bimproved\b': 'drove improvements in',
            r'\bled\b': 'championed'
        }
        
        for pattern, replacement in executive_enhancements.items():
            content = re.sub(pattern, replacement, content, flags=re.I)
        
        return content
    
    def _to_plain_text(self, structured_content: Dict[str, Any], options: FormattingOptions) -> str:
        """Convert to plain text format."""
        output = []
        
        for section in structured_content["sections"]:
            if options.include_headers and section["title"] != "Header":
                output.append(f"\n{section['title'].upper()}\n")
            
            content = section["content"]
            if options.include_bullets and section["title"] in ["Experience", "Skills", "Achievements"]:
                # Convert to bullet points
                lines = content.split('\n')
                content = '\n'.join(f"• {line}" if line.strip() and not line.startswith('•') else line for line in lines)
            
            output.append(content)
        
        return '\n'.join(output)
    
    def _to_markdown(self, structured_content: Dict[str, Any], options: FormattingOptions) -> str:
        """Convert to Markdown format."""
        output = []
        
        for section in structured_content["sections"]:
            if options.include_headers and section["title"] != "Header":
                output.append(f"\n## {section['title']}\n")
            
            content = section["content"]
            
            # Add emphasis for key terms
            if options.include_emphasis:
                content = re.sub(r'\b(\d+%|\$[\d,]+|[A-Z]{2,})\b', r'**\1**', content)
            
            # Convert to bullet points
            if options.include_bullets and section["title"] in ["Experience", "Skills", "Achievements"]:
                lines = content.split('\n')
                content = '\n'.join(f"- {line}" if line.strip() and not line.startswith('-') else line for line in lines)
            
            output.append(content)
        
        return '\n'.join(output)
    
    def _to_html(self, structured_content: Dict[str, Any], options: FormattingOptions) -> str:
        """Convert to HTML format."""
        style_config = structured_content.get("global_style", {})
        
        html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        body {{
            font-family: {style_config.get('fonts', ['Arial'])[0]}, sans-serif;
            color: {style_config.get('colors', {}).get('primary', '#000000')};
            line-height: {self._get_line_height(options.line_spacing)};
            max-width: 800px;
            margin: 0 auto;
            padding: 20px;
        }}
        .section {{
            margin-bottom: 20px;
        }}
        .section-title {{
            color: {style_config.get('colors', {}).get('accent', '#333333')};
            font-weight: bold;
            font-size: 1.2em;
            margin-bottom: 10px;
        }}
        .highlight {{
            background-color: #f0f8ff;
            padding: 2px 4px;
        }}
    </style>
</head>
<body>
"""
        
        for section in structured_content["sections"]:
            html += '<div class="section">\n'
            
            if options.include_headers and section["title"] != "Header":
                html += f'<div class="section-title">{section["title"]}</div>\n'
            
            content = section["content"]
            
            # Add emphasis
            if options.include_emphasis:
                content = re.sub(r'\b(\d+%|\$[\d,]+)\b', r'<span class="highlight">\1</span>', content)
            
            # Convert line breaks
            content = content.replace('\n', '<br>\n')
            
            html += f'<div>{content}</div>\n'
            html += '</div>\n'
        
        html += "</body>\n</html>"
        return html
    
    def _to_latex(self, structured_content: Dict[str, Any], options: FormattingOptions) -> str:
        """Convert to LaTeX format."""
        latex = r"""\documentclass[11pt]{article}
\usepackage[utf8]{inputenc}
\usepackage[margin=1in]{geometry}
\usepackage{enumitem}
\usepackage{titlesec}

\titleformat{\section}{\large\bfseries}{\thesection}{1em}{}
\setlength{\parindent}{0pt}
\setlength{\parskip}{6pt}

\begin{document}
"""
        
        for section in structured_content["sections"]:
            if options.include_headers and section["title"] != "Header":
                latex += f"\n\\section{{{section['title']}}}\n"
            
            content = section["content"]
            
            # Escape LaTeX special characters
            content = content.replace('&', r'\&').replace('%', r'\%').replace('$', r'\$')
            content = content.replace('#', r'\#').replace('^', r'\^{}').replace('_', r'\_')
            
            # Convert bullets to itemize
            if options.include_bullets and section["title"] in ["Experience", "Skills", "Achievements"]:
                lines = content.split('\n')
                if any(line.strip().startswith('•') or line.strip().startswith('-') for line in lines):
                    latex += "\\begin{itemize}[leftmargin=*]\n"
                    for line in lines:
                        line = line.strip()
                        if line.startswith('•') or line.startswith('-'):
                            latex += f"\\item {line[1:].strip()}\n"
                        elif line:
                            latex += f"\\item {line}\n"
                    latex += "\\end{itemize}\n"
                else:
                    latex += content + "\n"
            else:
                latex += content + "\n"
        
        latex += "\n\\end{document}"
        return latex
    
    def _to_json(self, structured_content: Dict[str, Any], options: FormattingOptions) -> str:
        """Convert to JSON format."""
        json_structure = {
            "document_type": structured_content.get("type", "unknown"),
            "sections": [],
            "metadata": {
                "generated_at": datetime.now().isoformat(),
                "format": "json_structured",
                "style": options.style.value
            }
        }
        
        for section in structured_content["sections"]:
            section_data = {
                "title": section["title"],
                "content": section["content"],
                "formatting": section.get("formatting", {}),
                "word_count": len(section["content"].split())
            }
            
            # Parse bullets if present
            if section["title"] in ["Experience", "Skills", "Achievements"]:
                lines = section["content"].split('\n')
                bullets = [line.strip()[1:].strip() for line in lines if line.strip().startswith(('•', '-'))]
                if bullets:
                    section_data["bullets"] = bullets
            
            json_structure["sections"].append(section_data)
        
        return json.dumps(json_structure, indent=2)
    
    def _get_line_height(self, spacing: str) -> str:
        """Get CSS line height for spacing option."""
        spacing_map = {
            "single": "1.2",
            "1.5": "1.5",
            "double": "2.0"
        }
        return spacing_map.get(spacing, "1.2")
    
    def _get_styling_info(self, options: FormattingOptions) -> Dict[str, Any]:
        """Get styling information for the generated content."""
        style_config = self.style_templates[options.style]
        
        return {
            "recommended_fonts": style_config["fonts"],
            "color_scheme": style_config["colors"],
            "style_characteristics": {
                "tone": style_config["tone"],
                "structure": style_config["structure"],
                "spacing": style_config["spacing"]
            },
            "format_specific_notes": self._get_format_notes(options.output_format)
        }
    
    def _get_format_notes(self, output_format: OutputFormat) -> List[str]:
        """Get format-specific notes and recommendations."""
        notes = {
            OutputFormat.PLAIN_TEXT: [
                "Best for ATS compatibility",
                "Easy to copy-paste into forms",
                "Universal compatibility"
            ],
            OutputFormat.MARKDOWN: [
                "Great for version control",
                "Easy to convert to other formats",
                "Readable in plain text"
            ],
            OutputFormat.HTML: [
                "Perfect for web display",
                "Supports rich formatting",
                "Can be styled with CSS"
            ],
            OutputFormat.LATEX: [
                "Professional academic formatting",
                "High-quality PDF output",
                "Precise typography control"
            ],
            OutputFormat.JSON_STRUCTURED: [
                "Machine-readable format",
                "Easy to parse and process",
                "Structured data extraction"
            ]
        }
        return notes.get(output_format, [])
    
    def _get_download_suggestions(self, options: FormattingOptions) -> Dict[str, str]:
        """Get download suggestions for the format."""
        suggestions = {
            OutputFormat.PLAIN_TEXT: {"extension": ".txt", "mime_type": "text/plain"},
            OutputFormat.MARKDOWN: {"extension": ".md", "mime_type": "text/markdown"},
            OutputFormat.HTML: {"extension": ".html", "mime_type": "text/html"},
            OutputFormat.LATEX: {"extension": ".tex", "mime_type": "application/x-latex"},
            OutputFormat.JSON_STRUCTURED: {"extension": ".json", "mime_type": "application/json"}
        }
        return suggestions.get(options.output_format, {"extension": ".txt", "mime_type": "text/plain"})

# Global multimodal generator instance
multimodal_generator = MultiModalGenerator()

def generate_formatted_content(base_content: str,
                             content_type: str,
                             output_format: str = "plain_text",
                             style: str = "professional",
                             formatting_options: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Generate content in specified format with styling."""
    
    # Parse options
    format_enum = OutputFormat(output_format)
    style_enum = ContentStyle(style)
    
    options = FormattingOptions(
        output_format=format_enum,
        style=style_enum,
        **(formatting_options or {})
    )
    
    return multimodal_generator.generate_multimodal_content(
        base_content=base_content,
        content_type=content_type,
        formatting_options=options
    )
