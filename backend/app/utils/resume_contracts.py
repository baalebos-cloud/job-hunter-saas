"""Shared generation/validation contracts. All fields are required for Groq strict mode."""
from typing import Literal
from pydantic import BaseModel, ConfigDict


class Contract(BaseModel):
    model_config = ConfigDict(strict=True, extra='forbid')


class SkillGroup(Contract):
    """One skill category as the resume names it (e.g. "CI/CD"), with its items.

    Strict JSON-schema mode cannot express a dict with arbitrary keys, so
    categories travel as a list of groups; ats_engine converts them to the
    ``{category: [items]}`` dict the rest of the pipeline uses.
    """
    category: str
    items: list[str]


class Experience(Contract):
    role: str
    company: str
    dates: str
    bullets: list[str]


class ExtractedExperience(Experience):
    location: str
    environment: str


class Project(Contract):
    title: str
    subtitle: str
    tech: str
    bullets: list[str]


class Education(Contract):
    degree: str
    institution: str
    year: str


class ExtractedResume(Contract):
    name: str
    title: str
    contact: str
    summary: str
    experience: list[ExtractedExperience]
    projects: list[Project]
    skills: list[SkillGroup]
    certifications: list[str]
    education: list[Education]
    additional_information: str


class ResumeRewrite(Contract):
    optimized_summary: str
    optimized_experience: list[Experience]
    optimized_skills: list[SkillGroup]
    confirmation_questions: list[str]
    suggestions_applied: list[str]


class Requirement(Contract):
    phrase: str
    priority: Literal['required', 'preferred']


class Requirements(Contract):
    requirements: list[Requirement]
