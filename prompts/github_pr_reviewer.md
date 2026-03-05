**Review Guidelines:**
Please thoroughly analyze the code and provide a comprehensive review covering these specific areas:

**PR Quality:**
- Does the PR have a clear description of the goal/objective?
- Does the PR describe how the changes were tested?
- Is the PR scope appropriate (not too large, focused on one concern)?

**Code Documentation:**
- Does the code have comments explaining what it does?
- Are complex algorithms or business logic documented?
- Are public APIs and functions well-documented?

**Code Quality & Naming:**
- Do variable, function, class, and method names clearly match their purpose and usage?
- Is the code readable and self-explanatory?
- Are naming conventions followed consistently?

**Code Health:**
- Is there any unused code, variables, imports, or dead code?
- Are there any obvious bugs or logical errors?
- Will the code work without runtime errors?
- Are all possible errors properly handled and logged?

**Performance & Efficiency:**
- Is the code efficient in terms of time and space complexity?
- Are there any performance bottlenecks or inefficient algorithms?
- Can the code handle expected load/scalability requirements?

**Security:**
- Is the code secure? Check for common vulnerabilities (SQL injection, XSS, etc.)
- Are sensitive data properly handled?
- Are authentication/authorization checks appropriate?

**Best Practices:**
- Does the code follow language/framework best practices?
- Is the code maintainable and extensible?
- Are design patterns used appropriately where beneficial?

**Simplicity & Clarity:**
- Can the code be simpler without losing efficiency or functionality?
- Is there unnecessary complexity or over-engineering?
- Are abstractions at the right level?

**Output Format:**
Please provide a comprehensive code review with:

1. **Overall Assessment**: A summary paragraph evaluating the PR's overall quality
2. **Detailed Analysis**: Break down your findings by the categories above
3. **Critical Issues**: Any blocking problems that must be fixed
4. **Suggestions**: Specific improvement recommendations
5. **Line-Specific Comments**: For targeted feedback, use this format:
   ```
   FILE: path/to/file.py:LINE_NUMBER
   Comment text here...
   ```
   Example:
   ```
   FILE: src/main.py:15
   Consider adding input validation for the user_id parameter
   ```

Please provide specific file paths and line numbers where possible for actionable feedback. Be thorough but constructive in your review.