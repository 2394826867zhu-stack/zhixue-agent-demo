---
name: find-skills
description: Find, discover, and install Claude Code skills from the official Anthropic skills marketplace and other sources. Use this skill whenever the user asks "is there a skill for X", "find me a skill that can do X", "how do I install a skill", "what skills are available", or wants to discover new capabilities that might exist as installable skills. Also use when the user asks about extending Claude Code with new abilities.
---

# Find Skills

A skill for discovering and installing Claude Code skills from the Anthropic marketplace and community.

## What are Skills?

Skills are folders containing a `SKILL.md` file with instructions that give Claude specialized capabilities. They live in:
- **Project-level**: `.claude/skills/<skill-name>/SKILL.md` (this project only)
- **User-level**: `~/.claude/skills/<skill-name>/SKILL.md` (all your projects)

## Official Anthropic Skills Marketplace

The official source is: **https://github.com/anthropics/skills**

### Available skills (as of 2026):

| Skill | Description |
|-------|-------------|
| `skill-creator` | Create, test, and improve new skills with eval framework |
| `pdf` | Extract, analyze, and transform PDF files |
| `docx` | Read, edit, and generate Word documents |
| `xlsx` | Analyze and manipulate Excel spreadsheets |
| `pptx` | Create and modify PowerPoint presentations |
| `frontend-design` | Build polished React/HTML UI components |
| `canvas-design` | Create visual designs and graphics |
| `algorithmic-art` | Generate generative/algorithmic artwork |
| `mcp-builder` | Build and configure MCP servers |
| `claude-api` | Use the Claude API and Anthropic SDK |
| `webapp-testing` | End-to-end web application testing |
| `doc-coauthoring` | Collaborative document writing |
| `internal-comms` | Draft internal communications |
| `brand-guidelines` | Apply brand guidelines to content |
| `slack-gif-creator` | Create animated GIFs for Slack |
| `theme-factory` | Generate design themes |
| `web-artifacts-builder` | Build interactive web artifacts |

## How to Install Skills

### Method 1: Plugin marketplace (recommended)

```
/plugin marketplace add anthropics/skills
/plugin install skill-creator@anthropic-agent-skills
```

### Method 2: Manual installation

1. Fetch the SKILL.md from GitHub
2. Create the directory: `.claude/skills/<skill-name>/`
3. Save the SKILL.md file there

Example for `pdf` skill:
```bash
mkdir -p .claude/skills/pdf
curl -o .claude/skills/pdf/SKILL.md \
  https://raw.githubusercontent.com/anthropics/skills/main/skills/pdf/SKILL.md
```

### Method 3: Create your own

Use `/skill-creator` to build a custom skill from scratch.

## Workflow: Finding the Right Skill

When the user describes what they want to do:

1. **Understand the task** — What is the user trying to accomplish?
2. **Search the marketplace** — Check if an official skill matches
3. **Recommend** — Suggest the best skill(s) for the job, with install instructions
4. **If no match** — Suggest using `/skill-creator` to build a custom one

## Quick Reference: Install by Category

**Document processing**: `pdf`, `docx`, `xlsx`, `pptx`
**UI/Design**: `frontend-design`, `canvas-design`, `algorithmic-art`, `theme-factory`
**Development**: `mcp-builder`, `claude-api`, `webapp-testing`, `web-artifacts-builder`
**Communication**: `doc-coauthoring`, `internal-comms`, `brand-guidelines`
**Skill management**: `skill-creator`, `find-skills`

## Checking Currently Installed Skills

The skills available in the current session are listed in the system context under `available_skills`. To see what's installed in the project:

```bash
ls .claude/skills/
```

For user-level skills:
```bash
ls ~/.claude/skills/
```

## Tips

- Skills are triggered automatically when you describe a task that matches the skill's description
- You can also explicitly invoke a skill by mentioning its name
- Project-level skills override user-level skills with the same name
- Use `skill-creator` to improve or extend any existing skill
