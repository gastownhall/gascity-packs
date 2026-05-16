#!/usr/bin/env node
"use strict";

const { McpServer, ResourceTemplate } = require("@modelcontextprotocol/sdk/server/mcp.js");
const { StdioServerTransport } = require("@modelcontextprotocol/sdk/server/stdio.js");
const { z } = require("zod/v3");
const fs = require("fs");
const path = require("path");

const CLAUDE_DIR = path.join(process.env.HOME, ".claude");
const PROJECTS_DIR = path.join(CLAUDE_DIR, "projects");

// The global memory dir is the project bucket for $HOME/.claude itself,
// computed by collapsing '/', '_', and '.' to '-' in the absolute path
// (the same rule enforced in enforcement/shared/utils/project-key.sh).
// Computing it dynamically avoids hard-coding any account name.
function projectKeyFromPath(absPath) {
  return absPath.replace(/^\//, "").replace(/[/_.]/g, "-");
}
const GLOBAL_MEMORY_DIR = path.join(
  PROJECTS_DIR,
  "-" + projectKeyFromPath(CLAUDE_DIR),
  "memory"
);

const VALID_TYPES = ["user", "feedback", "project", "reference"];

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function getMemoryDir(project) {
  if (!project) {
    return GLOBAL_MEMORY_DIR;
  }
  const sanitized = project.replace(/\//g, "-");
  return path.join(PROJECTS_DIR, sanitized, "memory");
}

function parseFrontmatter(content) {
  const fm = { name: "", description: "", type: "" };
  if (!content.startsWith("---")) {
    return { frontmatter: fm, body: content };
  }
  const endIdx = content.indexOf("---", 3);
  if (endIdx === -1) {
    return { frontmatter: fm, body: content };
  }
  const fmBlock = content.slice(3, endIdx).trim();
  let body = content.slice(endIdx + 3).trim();
  for (const line of fmBlock.split("\n")) {
    const colonIdx = line.indexOf(":");
    if (colonIdx === -1) continue;
    const key = line.slice(0, colonIdx).trim().toLowerCase();
    const val = line.slice(colonIdx + 1).trim();
    if (key === "name") fm.name = val;
    else if (key === "description") fm.description = val;
    else if (key === "type") fm.type = val;
  }
  return { frontmatter: fm, body };
}

function buildFileContent(name, description, type, content) {
  return `---\nname: ${name}\ndescription: ${description}\ntype: ${type}\n---\n\n${content}\n`;
}

function ensureDir(dir) {
  if (!fs.existsSync(dir)) {
    fs.mkdirSync(dir, { recursive: true });
  }
}

function listMemoryFiles(memDir) {
  if (!fs.existsSync(memDir)) {
    return [];
  }
  return fs.readdirSync(memDir).filter(
    (f) => f.endsWith(".md") && f !== "MEMORY.md"
  );
}

function updateMemoryIndex(memDir, filename, name, remove) {
  const indexPath = path.join(memDir, "MEMORY.md");
  let indexContent = "";
  if (fs.existsSync(indexPath)) {
    indexContent = fs.readFileSync(indexPath, "utf-8");
  } else {
    indexContent = "# MEMORY\n";
  }

  const linkLine = `- [${name}](${filename})`;
  const linkPattern = new RegExp(
    `^- \\[.*?\\]\\(${filename.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}\\).*$`,
    "m"
  );

  if (remove) {
    indexContent = indexContent.replace(linkPattern, "").replace(/\n{3,}/g, "\n\n").trim() + "\n";
  } else {
    if (linkPattern.test(indexContent)) {
      indexContent = indexContent.replace(linkPattern, linkLine);
    } else {
      indexContent = indexContent.trimEnd() + "\n" + linkLine + "\n";
    }
  }

  fs.writeFileSync(indexPath, indexContent, "utf-8");
}

function searchInContent(content, query) {
  const lowerQuery = query.toLowerCase();
  const lines = content.split("\n");
  const matches = [];
  for (let i = 0; i < lines.length; i++) {
    if (lines[i].toLowerCase().includes(lowerQuery)) {
      const start = Math.max(0, i - 1);
      const end = Math.min(lines.length, i + 2);
      matches.push(lines.slice(start, end).join("\n"));
    }
  }
  return matches;
}

function getProjectName(dirName) {
  return dirName.replace(/^-/, "/").replace(/-/g, "/");
}

// ---------------------------------------------------------------------------
// Server setup
// ---------------------------------------------------------------------------

const server = new McpServer(
  { name: "project-memory", version: "1.0.0" },
  {
    capabilities: {
      tools: {},
      resources: {}
    }
  }
);

// ---------------------------------------------------------------------------
// Tools
// ---------------------------------------------------------------------------

server.tool(
  "list_memories",
  "List all memories for a project or globally",
  {
    project: z.string().optional().describe("Project directory path (omit for global)"),
    type: z.enum(VALID_TYPES).optional().describe("Filter by type: user/feedback/project/reference")
  },
  (args) => {
    const memDir = getMemoryDir(args.project);
    const files = listMemoryFiles(memDir);
    const results = [];

    for (const file of files) {
      const filePath = path.join(memDir, file);
      const content = fs.readFileSync(filePath, "utf-8");
      const { frontmatter } = parseFrontmatter(content);
      if (args.type && frontmatter.type !== args.type) continue;
      results.push({
        filename: file,
        name: frontmatter.name,
        description: frontmatter.description,
        type: frontmatter.type
      });
    }

    return {
      content: [{
        type: "text",
        text: JSON.stringify(results, null, 2)
      }]
    };
  }
);

server.tool(
  "get_memory",
  "Read a specific memory file",
  {
    project: z.string().optional().describe("Project directory path (omit for global)"),
    filename: z.string().describe("The .md filename to read")
  },
  (args) => {
    const memDir = getMemoryDir(args.project);
    const filePath = path.join(memDir, args.filename);

    if (!fs.existsSync(filePath)) {
      return {
        content: [{ type: "text", text: `Error: Memory file not found: ${args.filename}` }],
        isError: true
      };
    }

    const content = fs.readFileSync(filePath, "utf-8");
    return {
      content: [{ type: "text", text: content }]
    };
  }
);

server.tool(
  "save_memory",
  "Create or update a memory file with frontmatter",
  {
    project: z.string().optional().describe("Project directory path (omit for global)"),
    filename: z.string().describe("The .md filename"),
    name: z.string().describe("Memory name"),
    description: z.string().describe("Memory description"),
    type: z.enum(VALID_TYPES).describe("Memory type: user/feedback/project/reference"),
    content: z.string().describe("Memory content (markdown)")
  },
  (args) => {
    const memDir = getMemoryDir(args.project);
    ensureDir(memDir);

    const filePath = path.join(memDir, args.filename);
    const fileContent = buildFileContent(args.name, args.description, args.type, args.content);
    fs.writeFileSync(filePath, fileContent, "utf-8");

    updateMemoryIndex(memDir, args.filename, args.name, false);

    return {
      content: [{ type: "text", text: `Saved memory: ${args.filename} in ${memDir}` }]
    };
  }
);

server.tool(
  "delete_memory",
  "Remove a memory file",
  {
    project: z.string().optional().describe("Project directory path (omit for global)"),
    filename: z.string().describe("The .md filename to delete")
  },
  (args) => {
    const memDir = getMemoryDir(args.project);
    const filePath = path.join(memDir, args.filename);

    if (!fs.existsSync(filePath)) {
      return {
        content: [{ type: "text", text: `Error: Memory file not found: ${args.filename}` }],
        isError: true
      };
    }

    const content = fs.readFileSync(filePath, "utf-8");
    const { frontmatter } = parseFrontmatter(content);

    fs.unlinkSync(filePath);
    updateMemoryIndex(memDir, args.filename, frontmatter.name || args.filename, true);

    return {
      content: [{ type: "text", text: `Deleted memory: ${args.filename}` }]
    };
  }
);

server.tool(
  "search_memories",
  "Search across all memories by content or frontmatter",
  {
    query: z.string().describe("Search query (case-insensitive)"),
    project: z.string().optional().describe("Search specific project (omit to search all)"),
    type: z.enum(VALID_TYPES).optional().describe("Filter by type")
  },
  (args) => {
    const dirsToSearch = [];

    if (args.project) {
      dirsToSearch.push({ project: args.project, dir: getMemoryDir(args.project) });
    } else {
      // Search global
      dirsToSearch.push({ project: "(global)", dir: GLOBAL_MEMORY_DIR });
      // Search all project memory dirs
      if (fs.existsSync(PROJECTS_DIR)) {
        for (const entry of fs.readdirSync(PROJECTS_DIR)) {
          const memDir = path.join(PROJECTS_DIR, entry, "memory");
          if (fs.existsSync(memDir) && fs.statSync(memDir).isDirectory()) {
            dirsToSearch.push({ project: getProjectName(entry), dir: memDir });
          }
        }
      }
    }

    const results = [];

    for (const { project, dir } of dirsToSearch) {
      const files = listMemoryFiles(dir);
      for (const file of files) {
        const filePath = path.join(dir, file);
        const content = fs.readFileSync(filePath, "utf-8");
        const { frontmatter, body } = parseFrontmatter(content);

        if (args.type && frontmatter.type !== args.type) continue;

        const snippets = searchInContent(content, args.query);
        if (snippets.length > 0) {
          results.push({
            project,
            filename: file,
            name: frontmatter.name,
            type: frontmatter.type,
            snippets: snippets.slice(0, 3)
          });
        }
      }

      // Also search MEMORY.md index
      const indexPath = path.join(dir, "MEMORY.md");
      if (fs.existsSync(indexPath)) {
        const indexContent = fs.readFileSync(indexPath, "utf-8");
        const snippets = searchInContent(indexContent, args.query);
        if (snippets.length > 0) {
          results.push({
            project,
            filename: "MEMORY.md",
            name: "Memory Index",
            type: "index",
            snippets: snippets.slice(0, 3)
          });
        }
      }
    }

    return {
      content: [{
        type: "text",
        text: results.length > 0
          ? JSON.stringify(results, null, 2)
          : `No memories found matching "${args.query}"`
      }]
    };
  }
);

server.tool(
  "list_projects",
  "List all projects that have memory directories",
  {},
  () => {
    const results = [];

    if (!fs.existsSync(PROJECTS_DIR)) {
      return {
        content: [{ type: "text", text: "No projects directory found." }],
        isError: true
      };
    }

    for (const entry of fs.readdirSync(PROJECTS_DIR)) {
      const memDir = path.join(PROJECTS_DIR, entry, "memory");
      if (fs.existsSync(memDir) && fs.statSync(memDir).isDirectory()) {
        const files = listMemoryFiles(memDir);
        results.push({
          project: getProjectName(entry),
          directoryName: entry,
          memoryCount: files.length,
          memories: files
        });
      }
    }

    return {
      content: [{
        type: "text",
        text: JSON.stringify(results, null, 2)
      }]
    };
  }
);

server.tool(
  "get_preferences",
  "Get user preferences and feedback memories",
  {
    project: z.string().optional().describe("Project directory path (omit for global)")
  },
  (args) => {
    const memDir = getMemoryDir(args.project);
    const files = listMemoryFiles(memDir);
    const results = [];

    for (const file of files) {
      const filePath = path.join(memDir, file);
      const content = fs.readFileSync(filePath, "utf-8");
      const { frontmatter, body } = parseFrontmatter(content);
      if (frontmatter.type === "user" || frontmatter.type === "feedback") {
        results.push({
          filename: file,
          name: frontmatter.name,
          type: frontmatter.type,
          content: body
        });
      }
    }

    return {
      content: [{
        type: "text",
        text: results.length > 0
          ? JSON.stringify(results, null, 2)
          : "No preferences or feedback memories found."
      }]
    };
  }
);

server.tool(
  "save_preference",
  "Quick save a user preference or feedback",
  {
    project: z.string().optional().describe("Project directory path (omit for global)"),
    key: z.string().describe("Short identifier for the preference"),
    value: z.string().describe("The preference/feedback content"),
    type: z.enum(["user", "feedback"]).optional().describe("Type (default: feedback)")
  },
  (args) => {
    const memType = args.type || "feedback";
    const filename = `${memType}_${args.key}.md`;
    const memDir = getMemoryDir(args.project);
    ensureDir(memDir);

    const name = `${memType}: ${args.key}`;
    const description = `${memType === "user" ? "User preference" : "Feedback"}: ${args.key}`;
    const fileContent = buildFileContent(name, description, memType, args.value);

    const filePath = path.join(memDir, filename);
    fs.writeFileSync(filePath, fileContent, "utf-8");
    updateMemoryIndex(memDir, filename, name, false);

    return {
      content: [{ type: "text", text: `Saved ${memType} preference: ${filename} in ${memDir}` }]
    };
  }
);

// ---------------------------------------------------------------------------
// Resources
// ---------------------------------------------------------------------------

server.resource(
  "global-memories",
  "memory://global",
  { description: "List of global memories" },
  () => {
    const files = listMemoryFiles(GLOBAL_MEMORY_DIR);
    const results = [];
    for (const file of files) {
      const filePath = path.join(GLOBAL_MEMORY_DIR, file);
      const content = fs.readFileSync(filePath, "utf-8");
      const { frontmatter } = parseFrontmatter(content);
      results.push({
        filename: file,
        name: frontmatter.name,
        description: frontmatter.description,
        type: frontmatter.type
      });
    }

    // Also include the MEMORY.md index content
    let indexContent = "";
    const indexPath = path.join(GLOBAL_MEMORY_DIR, "MEMORY.md");
    if (fs.existsSync(indexPath)) {
      indexContent = fs.readFileSync(indexPath, "utf-8");
    }

    return {
      contents: [{
        uri: "memory://global",
        mimeType: "application/json",
        text: JSON.stringify({ index: indexContent, memories: results }, null, 2)
      }]
    };
  }
);

server.resource(
  "all-projects",
  "memory://projects",
  { description: "List of projects with memories" },
  () => {
    const results = [];
    if (fs.existsSync(PROJECTS_DIR)) {
      for (const entry of fs.readdirSync(PROJECTS_DIR)) {
        const memDir = path.join(PROJECTS_DIR, entry, "memory");
        if (fs.existsSync(memDir) && fs.statSync(memDir).isDirectory()) {
          const files = listMemoryFiles(memDir);
          results.push({
            project: getProjectName(entry),
            directoryName: entry,
            memoryCount: files.length
          });
        }
      }
    }

    return {
      contents: [{
        uri: "memory://projects",
        mimeType: "application/json",
        text: JSON.stringify(results, null, 2)
      }]
    };
  }
);

server.resource(
  "project-memories",
  new ResourceTemplate("memory://project/{projectName}", { list: undefined }),
  { description: "Memories for a specific project" },
  (uri, variables) => {
    const projectName = variables.projectName;
    const memDir = path.join(PROJECTS_DIR, projectName, "memory");
    const results = [];

    if (fs.existsSync(memDir)) {
      const files = listMemoryFiles(memDir);
      for (const file of files) {
        const filePath = path.join(memDir, file);
        const content = fs.readFileSync(filePath, "utf-8");
        const { frontmatter } = parseFrontmatter(content);
        results.push({
          filename: file,
          name: frontmatter.name,
          description: frontmatter.description,
          type: frontmatter.type
        });
      }
    }

    let indexContent = "";
    const indexPath = path.join(memDir, "MEMORY.md");
    if (fs.existsSync(indexPath)) {
      indexContent = fs.readFileSync(indexPath, "utf-8");
    }

    return {
      contents: [{
        uri: uri.href,
        mimeType: "application/json",
        text: JSON.stringify({ project: projectName, index: indexContent, memories: results }, null, 2)
      }]
    };
  }
);

// ---------------------------------------------------------------------------
// Start server
// ---------------------------------------------------------------------------

async function main() {
  const transport = new StdioServerTransport();
  await server.connect(transport);
  console.error("project-memory MCP server running on stdio");
}

main().catch((err) => {
  console.error("Fatal error:", err);
  process.exit(1);
});
