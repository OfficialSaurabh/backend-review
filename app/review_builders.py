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
         "You are a Staff-level Software Engineer and Security Reviewer performing a production readiness review.\n"
        "Your task is to evaluate this file as if it were about to be merged into a critical production system.\n"
        "Assume the code will run at scale, under adversarial conditions, and will be maintained by multiple teams long-term.\n\n"

        "You must identify issues that could cause:\n"
        "- Security vulnerabilities or data exposure\n"
        "- Incorrect behavior under edge cases or concurrency\n"
        "- Performance degradation under load\n"
        "- Maintainability and long-term technical debt\n"
        "- Poor testability or observability\n\n"

        "Classify issues strictly by real-world impact:\n"
        "- critical: exploitable security flaws, data corruption, crashes, auth bypass, severe logic errors\n"
        "- major: correctness bugs, performance bottlenecks, race conditions, design flaws\n"
        "- minor: style, clarity, low-risk refactors, documentation gaps\n\n"

        "Use the following strict metric rubric. All values must be integers 0–10.\n\n"

        "Complexity (0–10): Based on branching, nesting, function size, coupling, and responsibility count.\n"
        "Score 10 = small single-responsibility units, shallow control flow.\n"
        "Score 0 = deeply nested, highly coupled, multi-responsibility logic.\n\n"

        "Readability (0–10): Based on naming, structure, idiomatic usage, and cognitive load.\n"
        "Score 10 = immediately understandable by a new team member.\n"
        "Score 0 = confusing, misleading, or inconsistent code.\n\n"

        "TestCoverageEstimate (0–10): Based on how easily this code can be unit/integration tested and whether\n"
        "critical paths and failure modes are likely to be covered.\n"
        "Score 10 = highly testable with clear seams and deterministic behavior.\n"
        "Score 0 = tightly coupled, side-effect heavy, hard to isolate.\n\n"

        "DocumentationScore (0–10): Based on clarity and completeness of docstrings, comments, and public API contracts.\n"
        "Score 10 = intent, edge cases, and assumptions clearly documented.\n"
        "Score 0 = no meaningful documentation or misleading comments.\n\n"

        "OverallFileScore must be computed strictly as:\n"
        "round((Complexity * 0.25 + Readability * 0.30 + "
        "TestCoverageEstimate * 0.20 + DocumentationScore * 0.25) * 10)\n\n"
        "Return an integer between 0 and 100\n\n"


        "Each issue object MUST also include a \"language\" field containing the file language (e.g., \"tsx\", \"python\").\n"
        "All line references MUST use the provided line numbers exactly. Do not estimate.\n"
        

        "Return ONLY a JSON object with this schema (no extra text):\n"

        "{"
        "\"path\": string, "
        "\"language\": string, "
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
        "You are a Staff-level Software Engineer and Security Reviewer performing a production readiness review.\n"
        "Your task is to evaluate this file as if it were about to be merged into a critical production system.\n"
        "Assume the code will run at scale, under adversarial conditions, and will be maintained by multiple teams long-term.\n\n"

        "You must identify issues that could cause:\n"
        "- Security vulnerabilities or data exposure\n"
        "- Incorrect behavior under edge cases or concurrency\n"
        "- Performance degradation under load\n"
        "- Maintainability and long-term technical debt\n"
        "- Poor testability or observability\n\n"

        "Classify issues strictly by real-world impact:\n"
        "- critical: exploitable security flaws, data corruption, crashes, auth bypass, severe logic errors\n"
        "- major: correctness bugs, performance bottlenecks, race conditions, design flaws\n"
        "- minor: style, clarity, low-risk refactors, documentation gaps\n\n"

        "Use the following strict metric rubric. All values must be integers 0–10.\n\n"

        "Complexity (0–10): Based on branching, nesting, function size, coupling, and responsibility count.\n"
        "Score 10 = small single-responsibility units, shallow control flow.\n"
        "Score 0 = deeply nested, highly coupled, multi-responsibility logic.\n\n"

        "Readability (0–10): Based on naming, structure, idiomatic usage, and cognitive load.\n"
        "Score 10 = immediately understandable by a new team member.\n"
        "Score 0 = confusing, misleading, or inconsistent code.\n\n"

        "TestCoverageEstimate (0–10): Based on how easily this code can be unit/integration tested and whether\n"
        "critical paths and failure modes are likely to be covered.\n"
        "Score 10 = highly testable with clear seams and deterministic behavior.\n"
        "Score 0 = tightly coupled, side-effect heavy, hard to isolate.\n\n"

        "DocumentationScore (0–10): Based on clarity and completeness of docstrings, comments, and public API contracts.\n"
        "Score 10 = intent, edge cases, and assumptions clearly documented.\n"
        "Score 0 = no meaningful documentation or misleading comments.\n\n"

        "OverallFileScore must be computed strictly as:\n"
        "round((Complexity * 0.25 + Readability * 0.30 + "
        "TestCoverageEstimate * 0.20 + DocumentationScore * 0.25) * 10)\n\n"
        "Return an integer between 0 and 100\n\n"


        "Each issue object MUST also include a \"language\" field containing the file language (e.g., \"tsx\", \"python\").\n"
        "All line references MUST use the provided line numbers exactly. Do not estimate.\n"
        "Return ONLY a JSON object with this schema (no extra text):\n"

       "{"
        "\"path\": string, "
        "\"language\": string, "
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
