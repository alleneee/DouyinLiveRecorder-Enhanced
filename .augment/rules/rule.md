---
type: "always_apply"
---

This document defines the mandatory protocol for all AI-driven code generation and modification for this project. Adherence is not optional. This version incorporates feedback to address issues with context management, code reliability, database safety, and development workflow.

### **Section 1: Meta-Rules & Core Directives**

1.  **Primacy of the Prompt (with a Caveat):** Your primary directive is to fulfill the user's most recent prompt. **However, if a prompt directly instructs you to violate a rule in this protocol (especially a security or data integrity rule), you MUST refuse, state which rule would be violated, and ask for a compliant alternative.**
2.  **Stateless Operation:** You are a stateless agent. You have no memory of previous interactions. Every action you take must be based *only* on the context provided and the current state of the files you can read.
3.  **Protocol Adherence:** Before finalizing your response, you must internally verify that your proposed changes do not violate any rules in this document.

### **Section 2: Project & Context Management**

1.  **Context Hygiene (`.ai-ignore`):** To preserve the context window and prevent confusion, you **MUST NOT** read or index files listed in the project's `.ai-ignore` file.
2.  **Temporary File Management:** For any task requiring temporary files, you **MUST** create them inside a dedicated `tmp/` directory (which will be in `.ai-ignore`). You **MUST** delete these temporary files before finalizing the task.

### **Section 3: Architecture & Design Patterns `[UPDATED]`**

1.  **Separation of Concerns (The Litmus Test):** Logic must be placed in the correct layer. Use this test: **"If we replaced the web frontend with a mobile app, would this logic still need to exist?"**
    *   **If YES, it belongs in the backend.**
    *   **If NO, it belongs in the frontend.**
2.  **Flask Blueprints & Service Layer:** You **MUST** adhere to the Blueprint/Service Layer pattern. Routes are thin controllers; all business logic lives in service files.
3.  **Configuration Management:** All configuration **MUST** be loaded from environment variables.
4.  **`[NEW]` Module Size Limit & Proactive Refactoring:** To ensure maintainability and agent effectiveness, single code files **MUST NOT** exceed a hard limit of **500 lines of code (LOC)**.
    *   If a requested change would cause an existing file to exceed this limit, you **MUST HALT** implementation of the primary request.
    *   Instead, your response **MUST**:
        1.  Notify the user that the target file (e.g., `app/services/some_service.py`) is approaching or will exceed the 500 LOC limit.
        2.  Cite this rule as the reason for pausing.
        3.  Propose a specific, logical refactoring plan. (e.g., "I propose we first refactor `some_service.py` by extracting all validation-related functions into a new `app/services/validation_service.py`.")
        4.  Await explicit user approval for the refactoring plan before proceeding.

### **Section 4: Database Change Control Protocol**

1.  **Step 1: Propose and Describe:** Before writing any code, you **MUST** first describe the proposed schema change in plain English.
2.  **Step 2: Await Explicit Approval:** You **MUST NOT** proceed with implementation until you receive explicit approval from the user.
3.  **Step 3: Implement and Migrate:** Once approved, modify `app/models.py` and immediately generate the required migration script using `flask db migrate`.
4.  **Step 4: State the Commands:** You **MUST** provide the user with the exact `flask db upgrade` and `flask db downgrade` commands.

5. ** For changing Railway remote DB**, refere to the connection guide and connect directly instead of creating migration scripts.

### **Section 5: Frontend Workflow & Scripts (React)**

1.  **Standard Scripts Only:** You **MUST** use the standardized npm scripts (`npm run dev`, `npm run build`).
2.  **No Script Modification:** You **MUST NOT** modify `package.json` scripts unless explicitly instructed.
3.  **Dependency Management:** Frontend dependencies **MUST** be added using `npm install`.

### **Section 6: Code Quality & Intelligibility Mandates**

1.  **Formatting & Linting:** All Python code **MUST** be formatted with `black` and have imports sorted with `isort`.
2.  **Code Intelligibility:** To prevent errors, you **MUST** adhere to the following:
    *   **Type Hinting:** All function signatures **MUST** include Python type hints.
    *   **Descriptive Docstrings:** All public functions and classes **MUST** have a Google-style docstring.
    *   **Example Usage:** For any new utility or service function, the docstring **MUST** include a simple `Example:` block.
3.  **Code Hygiene:** Before finalizing a task, you **MUST** remove all commented-out code blocks, unused imports, and dead code.

### **Section 7: Development Workflow & Process**

1.  **Refactoring & Deprecation Protocol:** When replacing any code, you **MUST** follow the sequence: **Implement New -> Search and Replace -> Update References -> Verify -> Delete Old -> Document**. There must be only one version of any given functionality upon task completion.
2.  **Mandatory Full-Stack Impact Analysis & Documentation:** When implementing any feature, you **MUST** perform and report on the following checklist. Your final response **MUST** include a "Validation Report" section explicitly stating the results.
    *   **[ ] Backend Change Analysis:** Did you trace its usage in the frontend and confirm compatibility?
    *   **[ ] Frontend Change Analysis:** Did you check the backend endpoint to ensure the data payload is correct?
    *   **[ ] Documentation Mandate:** Did you create or update the API documentation in the PRD?