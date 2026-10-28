# Project handoff rule

Read `project_context.md` before working on this project. After each project task, update it with verified progress and the next action. Replace outdated text and remove superseded details rather than appending a log. Keep it concise, under roughly 2,500 words, so it remains usable as the primary handoff context in a new chat.

For every formal project report or document, read and follow the locked `reports/style.md`. Use `reports/builders/layout.py` for PDFs and the same visual rules for Word documents. Do not change the format unless Sudin explicitly requests it. Keep wording specific and modest about unverified work.

Use `src/solar_pv/` as the base package for application code, and place work in the existing responsibility-specific subpackages. Keep report builders in `reports/`, research in `research/`, tests in `tests/`, configuration in `configs/`, and local datasets or generated files outside the package. Add another subpackage only when a clear need appears.

Before creating any code, script, report, document, or asset, place it in the existing area that owns it. Keep the root limited to project-wide entry points and configuration. Add a new directory only for a clear purpose, and update `README.md` when the structure changes.
