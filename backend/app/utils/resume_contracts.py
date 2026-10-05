"""Shared generation/validation contracts. All fields are required for Groq strict mode."""
from typing import Literal
from pydantic import BaseModel, ConfigDict


class Contract(BaseModel):
    model_config = ConfigDict(strict=True, extra='forbid')


class Skills(Contract):
    Skills: list[str]


class Experience(Contract):
    role: str
    company: str
    dates: str
    bullets: list[str]


class ExtractedExperience(Experience):
    environment: str


class Project(Contract):
    title: str
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
    skills: Skills
    certifications: list[str]
    education: list[Education]
    additional_information: str


class ResumeRewrite(Contract):
    optimized_summary: str
    optimized_experience: list[Experience]
    optimized_skills: Skills
    confirmation_questions: list[str]
    suggestions_applied: list[str]


class Requirement(Contract):
    phrase: str
    priority: Literal['required', 'preferred']


class Requirements(Contract):
    requirements: list[Requirement]
