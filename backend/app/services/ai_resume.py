from openai import OpenAI

client = OpenAI()

def tailor_resume(job_description, resume):

    prompt = f"""
    Customize this resume for the job.

    Job:
    {job_description}

    Resume:
    {resume}
    """

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role":"user","content":prompt}]
    )

    return response.choices[0].message.content
