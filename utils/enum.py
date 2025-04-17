from enum import Enum

class ReportSource(str, Enum):
    """Report source enum"""
    Web = "web"
    Document = "document"


class ReportType(str, Enum):
    """Report type enum"""
    ResearchReport = "research_report"
    ResourceReport = "resource_report"
    OutlineReport = "outline_report"
    CustomReport = "custom_report"
    SubtopicReport = "subtopic_report"
    DetailedReport = "detailed_report"
    DeepResearch = "deep_research"


class Tone(str, Enum):
    """Tone enum"""
    Objective = "objective"
    Persuasive = "persuasive"
    Informative = "informative"
    Analytical = "analytical"
    Conversational = "conversational"
    Technical = "technical"
    Enthusiastic = "enthusiastic"