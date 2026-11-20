# Guidance for Claude

## Zero attribution

Nothing produced in this repository may identify an AI assistant as its author or source.

- Commits are authored and committed as ccsrvs@gmail.com, the repository owner's identity.
- Commit messages contain only the subject and a description of the change: no `Co-Authored-By` lines, session links or other trailers.
- Pull request titles and descriptions, issue text, review comments and replies carry no "Generated with" footers, session links or tool names.
- Code, comments, documentation and generated files do not mention the assistant or the tooling used to write them.

## CI runners

- Workflows run only on GitHub's standard hosted runners, which are free for
  this public repository. No larger runners (billed even here) and no
  self-hosted runners.
- `.github/scripts/standard-runners.py` lists the allowed labels and fails
  the `test` gate on any other. Add a label only after checking GitHub's
  runner reference lists it as standard for public repositories.
