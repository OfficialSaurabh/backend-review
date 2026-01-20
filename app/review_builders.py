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

        "Use the following strict scoring rubric for metrics. All values must be integers 0–10.\n"

        "Complexity (0–10): Measured from cyclomatic complexity, nesting depth, function length, "
        "and number of responsibilities. Score 10 = small single-purpose functions, shallow nesting, "
        "low branching. Score 0 = deeply nested, high branching, large god functions.\n"

        "Readability (0–10): Measured from naming clarity, formatting consistency, logical flow, "
        "and idiomatic language usage. Score 10 = self-documenting, clean, idiomatic code. "
        "Score 0 = confusing naming, inconsistent style, hard to follow logic.\n"

        "TestCoverageEstimate (0–10): Estimated from presence of tests, isolation of logic, "
        "mockability, and coverage of error paths. Score 10 = comprehensive automated tests likely. "
        "Score 0 = no testability or coverage indications.\n"

        "DocumentationScore (0–10): Measured from quality of docstrings, comments, "
        "and public API documentation. Score 10 = fully documented public and internal logic. "
        "Score 0 = undocumented or misleading documentation.\n"

        "OverallFileScore must be computed strictly as:\n"
        "(Complexity * 0.25 + Readability * 0.30 + "
        "TestCoverageEstimate * 0.20 + DocumentationScore * 0.25) * 10\n"

        "Each issue object MUST also include a \"language\" field containing the file language (e.g., \"tsx\", \"python\").\n"
        "All line references MUST use the provided line numbers exactly. Do not estimate.\n"
        

        "Return ONLY a JSON object with this schema (no extra text):\n"

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

        "Use the following strict scoring rubric for metrics. All values must be integers 0–10.\n"

        "Complexity (0–10): Measured from cyclomatic complexity, nesting depth, function length, "
        "and number of responsibilities. Score 10 = small single-purpose functions, shallow nesting, "
        "low branching. Score 0 = deeply nested, high branching, large god functions.\n"

        "Readability (0–10): Measured from naming clarity, formatting consistency, logical flow, "
        "and idiomatic language usage. Score 10 = self-documenting, clean, idiomatic code. "
        "Score 0 = confusing naming, inconsistent style, hard to follow logic.\n"

        "TestCoverageEstimate (0–10): Estimated from presence of tests, isolation of logic, "
        "mockability, and coverage of error paths. Score 10 = comprehensive automated tests likely. "
        "Score 0 = no testability or coverage indications.\n"

        "DocumentationScore (0–10): Measured from quality of docstrings, comments, "
        "and public API documentation. Score 10 = fully documented public and internal logic. "
        "Score 0 = undocumented or misleading documentation.\n"

        "OverallFileScore must be computed strictly as:\n"
        "(Complexity * 0.25 + Readability * 0.30 + "
        "TestCoverageEstimate * 0.20 + DocumentationScore * 0.25) * 10\n"

        "Each issue object MUST also include a \"language\" field containing the file language (e.g., \"tsx\", \"python\").\n"
        "All line references MUST use the provided line numbers exactly. Do not estimate.\n"
        "Return ONLY a JSON object with this schema (no extra text):\n"

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
