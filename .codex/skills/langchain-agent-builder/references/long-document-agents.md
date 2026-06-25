# Long Document Agent Notes

Use this reference when building LangChain / LangGraph agents for long `.docx`, PDF, Markdown, or text files.

## Practical Design

- Do not depend on one giant model call even when the advertised context window appears large enough.
- Parse source files into stable elements, for example paragraph/table/page ids.
- Chunk by headings, pages, sections, or records before falling back to character/token length.
- Preserve evidence ids in every chunk so model findings can be traced back to source.
- Keep overlap small and purposeful; too much overlap increases duplicate findings.
- Add a merge node that deduplicates findings and records unresolved cross-chunk checks.

## Suggested Graph

```text
load_inputs -> extract_elements -> chunk_elements -> review_chunks -> aggregate_report -> write_output
```

For high-risk review workflows, add:

```text
extract_claims -> cross_reference_claims -> final_quality_gate
```

## Chunk Prompt Checklist

- State the domain role.
- Include the relevant reference rules.
- Include one chunk only.
- Require evidence ids for every finding.
- Require labels: confirmed, suspected, needs cross-chunk review.
- Ask the model to say when no clear issue is found.

## Aggregate Prompt Checklist

- Summarize chunk coverage.
- Merge duplicate findings.
- Group by severity and theme.
- Preserve all evidence ids.
- List unresolved checks instead of pretending they are resolved.
