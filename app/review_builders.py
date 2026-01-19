def add_line_numbers(code: str) -> str:
    return "\n".join(
        f"{i+1}: {line}"
        for i, line in enumerate(code.splitlines())
    )


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
        "Each issue object MUST also include a \"language\" field containing the file language (e.g., \"tsx\", \"python\").\n"
        "All line references MUST use the provided line numbers exactly. Do not estimate.\n"

        "{"
        "\"path\": string, "
        "\"issues\": ["
        "{"
        "\"startLine\": number, "
        "\"endLine\": number, "
        "\"severity\": \"critical\"|\"major\"|\"minor\", "
        "\"type\": string, "
        "\"message\": string, "
        "\"codeSnippet\": string"
        "}"
        "], "
        "\"suggestions\": ["
        "{"
        "\"title\": string, "
        "\"explanation\": string, "
        "\"startLine\": number|null, "
        "\"endLine\": number|null, "
        "\"codeSnippet\": string|null, "
        "\"diff_example\": string|null"
        "}"
        "], "
        "\"metrics\": {"
        "\"complexity\": number, "
        "\"readability\": number, "
        "\"testCoverageEstimate\": number, "
        "\"documentationScore\": number"
        "}, "
        "\"overallFileScore\": number"
        "}\n\n"

        f"Project: {owner}/{repo}@{ref}\n"
        f"File: {filename}\n"
        f"Language: {language}\n\n"
        "Code (with exact line numbers, use these numbers only):\n"
        f"{add_line_numbers(content)}"

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
        "Each issue object MUST also include a \"language\" field containing the file language (e.g., \"tsx\", \"python\").\n"
        "All line references MUST use the provided line numbers exactly. Do not estimate.\n"

       "{"
        "\"path\": string, "
        "\"issues\": ["
        "{"
        "\"startLine\": number, "
        "\"endLine\": number, "
        "\"severity\": \"critical\"|\"major\"|\"minor\", "
        "\"type\": string, "
        "\"message\": string, "
        "\"codeSnippet\": string, "
        "\"language\": string"
        "}"
        "], "
        "\"suggestions\": ["
        "{"
        "\"title\": string, "
        "\"explanation\": string, "
        "\"startLine\": number|null, "
        "\"endLine\": number|null, "
        "\"codeSnippet\": string|null, "
        "\"diff_example\": string|null"
        "}"
        "], "
        "\"metrics\": {"
        "\"complexity\": number, "
        "\"readability\": number, "
        "\"testCoverageEstimate\": number, "
        "\"documentationScore\": number"
        "}, "
        "\"overallFileScore\": number"
        "}\n\n"
        f"Project: {owner}/{repo}@{ref}\n"
        f"File: {filename}\n"
        f"Language: {language}\n\n"
        "Code (with exact line numbers, use these numbers only):\n"
        f"{add_line_numbers(content)}"

    )
