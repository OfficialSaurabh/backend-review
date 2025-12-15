def build_file_prompt(
    owner: str,
    repo: str,
    ref: str,
    filename: str,
    language: str,
    content: str,
) -> str:
    return (
        "You are a senior software engineer and code reviewer.\n"
        "Analyze the following code file for structure, maintainability, "
        "correctness, security, performance, and documentation.\n"
        "Return ONLY a JSON object with this schema (no extra text):\n"
        '{'
        '"path": string, '
        '"issues": ['
        '{"line": number|null, '
        '"severity": "critical"|"major"|"minor", '
        '"type": string, '
        '"message": string}'
        '], '
        '"suggestions": ['
        '{"title": string, '
        '"explanation": string, '
        '"diff_example": string|null}'
        '], '
        '"metrics": {'
        '"complexity": number, '
        '"readability": number, '
        '"testCoverageEstimate": number, '
        '"documentationScore": number'
        '}, '
        '"overallFileScore": number'
        '}\n\n'
        f"Project: {owner}/{repo}@{ref}\n"
        f"File: {filename}\n"
        f"Language: {language}\n\n"
        "Code:\n"
        f"{content}"
    )

MAX_CHARS = 8000  # same as n8n

def build_project_prompt(
    owner: str,
    repo: str,
    ref: str,
    filename: str,
    language: str,
    content: str,
) -> str:
    # truncate like n8n
    if len(content) > MAX_CHARS:
        half = MAX_CHARS // 2
        content = (
            content[:half]
            + "\n\n// ... file truncated ...\n\n"
            + content[-half:]
        )

    return (
        "You are a senior software engineer and code reviewer.\n"
        "Analyze the following code file for structure, maintainability, "
        "correctness, security, performance, and documentation.\n"
        "Return ONLY a JSON object with this schema (no extra text):\n"
        "{"
        "\"path\": string, "
        "\"issues\": [{\"line\": number|null, "
        "\"severity\": \"critical\"|\"major\"|\"minor\", "
        "\"type\": string, "
        "\"message\": string}], "
        "\"suggestions\": [{\"title\": string, "
        "\"explanation\": string, "
        "\"diff_example\": string|null}], "
        "\"metrics\": {"
        "\"complexity\": number, "
        "\"readability\": number, "
        "\"testCoverageEstimate\": number, "
        "\"documentationScore\": number}, "
        "\"overallFileScore\": number"
        "}\n\n"
        f"Project: {owner}/{repo}@{ref}\n"
        f"File: {filename}\n"
        f"Language: {language}\n\n"
        "Code:\n"
        f"{content}"
    )
