import random

def generate_resume_fix(missing_keywords, job_title):
    """
    Generates professional bullet points to bridge the gap for missing skills.
    """
    suggestions = []
    
    # Professional Action Verbs for the "Global Tech" feel
    action_verbs = ["Spearheaded", "Optimized", "Architected", "Engineered", "Automated"]

    for skill in missing_keywords:
        verb = random.choice(action_verbs)
        
        # Templates based on common tech categories
        templates = [
            f"{verb} {skill} solutions to improve system reliability by 25% for a {job_title} project.",
            f"Integrated {skill} into the existing CI/CD pipeline, reducing deployment latency.",
            f"Led the migration of legacy services to a {skill}-based architecture, ensuring zero downtime.",
            f"Collaborated with cross-functional teams to implement {skill} best practices globally."
        ]
        
        suggestions.append({
            "skill": skill,
            "bullet_point": random.choice(templates)
        })

    return suggestions
