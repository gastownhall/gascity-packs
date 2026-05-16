#!/usr/bin/env node
const { Server } = require("@modelcontextprotocol/sdk/server/index.js");
const { StdioServerTransport } = require("@modelcontextprotocol/sdk/server/stdio.js");
const {
  CallToolRequestSchema,
  ListToolsRequestSchema,
  ListResourcesRequestSchema,
  ReadResourceRequestSchema,
  ListResourceTemplatesRequestSchema,
} = require("@modelcontextprotocol/sdk/types.js");
const fs = require("fs");
const path = require("path");

const GUIDELINES_DIR = path.join(process.env.HOME, ".claude", "guidelines");

// Language/extension to guideline file mapping
const LANGUAGE_MAP = {
  python: "python_guidelines",
  py: "python_guidelines",
  ".py": "python_guidelines",
  bash: "bash_guidelines",
  sh: "bash_guidelines",
  ".sh": "bash_guidelines",
  shell: "bash_guidelines",
  csharp: "csharp_guidelines",
  cs: "csharp_guidelines",
  ".cs": "csharp_guidelines",
  "c#": "csharp_guidelines",
  rust: "rust_guidelines",
  rs: "rust_guidelines",
  ".rs": "rust_guidelines",
  typescript: "frontend_guidelines",
  ts: "frontend_guidelines",
  ".ts": "frontend_guidelines",
  javascript: "frontend_guidelines",
  js: "frontend_guidelines",
  ".js": "frontend_guidelines",
  react: "frontend_guidelines",
  tsx: "frontend_guidelines",
  ".tsx": "frontend_guidelines",
  jsx: "frontend_guidelines",
  ".jsx": "frontend_guidelines",
  frontend: "frontend_guidelines",
  java: "maven_guidelines",
  maven: "maven_guidelines",
  sql: "sql_guidelines",
  ".sql": "sql_guidelines",
  powershell: "powershell_guidelines",
  ps1: "powershell_guidelines",
  ".ps1": "powershell_guidelines",
  pwsh: "powershell_guidelines",
  swift: "swift_guidelines",
  ".swift": "swift_guidelines",
  go: "go_guidelines",
  ".go": "go_guidelines",
  golang: "go_guidelines",
  docker: "docker_guidelines",
  dockerfile: "docker_guidelines",
  kubernetes: "kubernetes_guidelines",
  k8s: "kubernetes_guidelines",
  angular: "angular_guidelines",
  vue: "vue_nuxt_guidelines",
  nuxt: "vue_nuxt_guidelines",
  bicep: "bicep_guidelines",
  ".bicep": "bicep_guidelines",
  yaml: "kubernetes_guidelines",
  ".yaml": "kubernetes_guidelines",
  yml: "kubernetes_guidelines",
  ".yml": "kubernetes_guidelines",
};

function listGuidelineFiles() {
  if (!fs.existsSync(GUIDELINES_DIR)) {
    return [];
  }
  return fs
    .readdirSync(GUIDELINES_DIR)
    .filter((f) => f.endsWith(".xml"))
    .sort();
}

function parseGuidelineMetadata(filePath) {
  const content = fs.readFileSync(filePath, "utf-8");
  const stats = fs.statSync(filePath);
  const basename = path.basename(filePath, ".xml");

  let language = "";
  let domain = "";
  let version = "";

  const guidelinesMatch = content.match(/<guidelines\s+([^>]+)>/);
  if (guidelinesMatch) {
    const attrs = guidelinesMatch[1];
    const langMatch = attrs.match(/language="([^"]+)"/);
    if (langMatch) language = langMatch[1];
    const domainMatch = attrs.match(/domain="([^"]+)"/);
    if (domainMatch) domain = domainMatch[1];
    const versionMatch = attrs.match(/version="([^"]+)"/);
    if (versionMatch) version = versionMatch[1];
  }

  return {
    name: basename,
    filename: path.basename(filePath),
    language: language || domain || basename.replace(/_guidelines$/, "").replace(/_/g, " "),
    domain: domain || language || basename.replace(/_guidelines$/, "").replace(/_/g, " "),
    version,
    sizeBytes: stats.size,
  };
}

function searchInFile(filePath, query, contextLines) {
  const content = fs.readFileSync(filePath, "utf-8");
  const lines = content.split("\n");
  const lowerQuery = query.toLowerCase();
  const matches = [];

  for (let i = 0; i < lines.length; i++) {
    if (lines[i].toLowerCase().includes(lowerQuery)) {
      const start = Math.max(0, i - contextLines);
      const end = Math.min(lines.length - 1, i + contextLines);
      const contextBlock = [];
      for (let j = start; j <= end; j++) {
        const marker = j === i ? ">>>" : "   ";
        contextBlock.push(`${marker} ${j + 1}: ${lines[j]}`);
      }
      matches.push({
        line: i + 1,
        content: lines[i].trim(),
        context: contextBlock.join("\n"),
      });
    }
  }

  return matches;
}

function escapeRegex(str) {
  return str.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function extractRules(filePath, severity, section) {
  const content = fs.readFileSync(filePath, "utf-8");
  const rules = [];

  const ruleRegex = /<rule\s+([^>]*?)(?:\/>|>([\s\S]*?)<\/rule>)/g;
  let match;

  while ((match = ruleRegex.exec(content)) !== null) {
    const attrs = match[1];
    const body = match[2] || "";

    const idMatch = attrs.match(/id="([^"]+)"/);
    const sevMatch = attrs.match(/severity="([^"]+)"/);
    const enfMatch = attrs.match(/enforcement="([^"]+)"/);

    const ruleId = idMatch ? idMatch[1] : "unknown";
    const ruleSeverity = sevMatch ? sevMatch[1] : "info";
    const enforcement = enfMatch ? enfMatch[1] : "";

    if (severity && ruleSeverity !== severity) {
      continue;
    }

    if (section) {
      const sectionPattern = new RegExp(
        `<section[^>]*id="${escapeRegex(section)}"[^>]*>[\\s\\S]*?${escapeRegex(match[0])}`,
        "i"
      );
      if (!sectionPattern.test(content)) {
        const principlePattern = new RegExp(
          `<principle[^>]*id="${escapeRegex(section)}"[^>]*>[\\s\\S]*?${escapeRegex(match[0])}`,
          "i"
        );
        if (!principlePattern.test(content)) {
          continue;
        }
      }
    }

    const constraints = [];
    const constraintRegex = /<constraint[^>]*>([^<]*)<\/constraint>/g;
    let cMatch;
    while ((cMatch = constraintRegex.exec(body)) !== null) {
      constraints.push(cMatch[1].trim());
    }

    const descMatch = body.match(/<description>([^<]*)<\/description>/);
    const description = descMatch ? descMatch[1].trim() : "";

    rules.push({
      id: ruleId,
      severity: ruleSeverity,
      enforcement,
      description,
      constraints,
    });
  }

  return rules;
}

async function main() {
  const server = new Server(
    {
      name: "guidelines-retriever",
      version: "1.0.0",
    },
    {
      capabilities: {
        tools: {},
        resources: {},
      },
    }
  );

  server.setRequestHandler(ListToolsRequestSchema, async () => {
    return {
      tools: [
        {
          name: "list_guidelines",
          description:
            "List all available guideline XML files with their domains, language, version, and file size.",
          inputSchema: {
            type: "object",
            properties: {},
            required: [],
          },
        },
        {
          name: "get_guideline",
          description:
            "Get the full XML content of a specific guideline file by name (without .xml extension).",
          inputSchema: {
            type: "object",
            properties: {
              name: {
                type: "string",
                description:
                  'Guideline filename without extension, e.g. "python_guidelines"',
              },
            },
            required: ["name"],
          },
        },
        {
          name: "search_guidelines",
          description:
            "Search across all guideline XML files for a keyword or pattern (case-insensitive). Returns matching lines with surrounding context, grouped by file.",
          inputSchema: {
            type: "object",
            properties: {
              query: {
                type: "string",
                description: "Search string (case-insensitive)",
              },
              max_results: {
                type: "number",
                description:
                  "Maximum number of matches to return (default 20)",
              },
            },
            required: ["query"],
          },
        },
        {
          name: "get_rules",
          description:
            'Extract <rule> elements from guidelines, optionally filtered by severity ("error", "warning", "info"), section/principle id, or specific guideline file.',
          inputSchema: {
            type: "object",
            properties: {
              severity: {
                type: "string",
                description:
                  'Filter by severity: "error", "warning", or "info"',
                enum: ["error", "warning", "info"],
              },
              section: {
                type: "string",
                description:
                  "Filter by section or principle id attribute",
              },
              guideline: {
                type: "string",
                description:
                  'Specific guideline file name (without .xml), e.g. "python_guidelines"',
              },
            },
            required: [],
          },
        },
        {
          name: "get_guideline_for_language",
          description:
            'Smart lookup: given a file extension or language name (e.g. "python", "py", ".py", "bash", "csharp", "cs", "typescript", "tsx"), return the matching guideline content.',
          inputSchema: {
            type: "object",
            properties: {
              language: {
                type: "string",
                description:
                  'Language name, file extension, or shorthand (e.g. "python", "py", ".py", "bash", "sh", "csharp", "cs", "react", "tsx")',
              },
            },
            required: ["language"],
          },
        },
      ],
    };
  });

  server.setRequestHandler(CallToolRequestSchema, async (request) => {
    const { name, arguments: args } = request.params;

    try {
      switch (name) {
        case "list_guidelines": {
          const files = listGuidelineFiles();
          if (files.length === 0) {
            return {
              content: [
                {
                  type: "text",
                  text: `No guideline files found in ${GUIDELINES_DIR}`,
                },
              ],
            };
          }

          const metadata = files.map((f) =>
            parseGuidelineMetadata(path.join(GUIDELINES_DIR, f))
          );

          const lines = metadata.map(
            (m) =>
              `${m.name} | language: ${m.language} | version: ${m.version || "N/A"} | size: ${m.sizeBytes} bytes`
          );

          return {
            content: [
              {
                type: "text",
                text: `Found ${files.length} guideline files:\n\n${lines.join("\n")}`,
              },
            ],
          };
        }

        case "get_guideline": {
          const guideName = args.name;
          if (!guideName) {
            return {
              content: [{ type: "text", text: "Error: 'name' parameter is required" }],
              isError: true,
            };
          }

          const filePath = path.join(GUIDELINES_DIR, `${guideName}.xml`);
          if (!fs.existsSync(filePath)) {
            const available = listGuidelineFiles()
              .map((f) => path.basename(f, ".xml"))
              .join(", ");
            return {
              content: [
                {
                  type: "text",
                  text: `Error: Guideline "${guideName}" not found.\nAvailable: ${available}`,
                },
              ],
              isError: true,
            };
          }

          const fileContent = fs.readFileSync(filePath, "utf-8");
          return {
            content: [{ type: "text", text: fileContent }],
          };
        }

        case "search_guidelines": {
          const query = args.query;
          if (!query) {
            return {
              content: [{ type: "text", text: "Error: 'query' parameter is required" }],
              isError: true,
            };
          }

          const maxResults = args.max_results || 20;
          const files = listGuidelineFiles();
          const results = [];
          let totalMatches = 0;

          for (const file of files) {
            if (totalMatches >= maxResults) break;

            const filePath = path.join(GUIDELINES_DIR, file);
            const matches = searchInFile(filePath, query, 2);

            if (matches.length > 0) {
              const remaining = maxResults - totalMatches;
              const truncated = matches.slice(0, remaining);
              totalMatches += truncated.length;

              results.push({
                file: path.basename(file, ".xml"),
                matchCount: matches.length,
                shownCount: truncated.length,
                matches: truncated,
              });
            }
          }

          if (results.length === 0) {
            return {
              content: [
                {
                  type: "text",
                  text: `No matches found for "${query}" across ${files.length} guideline files.`,
                },
              ],
            };
          }

          const output = results
            .map((r) => {
              const header = `=== ${r.file} (${r.matchCount} matches${r.shownCount < r.matchCount ? `, showing ${r.shownCount}` : ""}) ===`;
              const body = r.matches
                .map((m) => `\n--- Line ${m.line} ---\n${m.context}`)
                .join("\n");
              return header + body;
            })
            .join("\n\n");

          return {
            content: [
              {
                type: "text",
                text: `Found ${totalMatches} matches across ${results.length} files:\n\n${output}`,
              },
            ],
          };
        }

        case "get_rules": {
          const severity = args.severity || null;
          const section = args.section || null;
          const guideline = args.guideline || null;

          let files;
          if (guideline) {
            const filePath = path.join(GUIDELINES_DIR, `${guideline}.xml`);
            if (!fs.existsSync(filePath)) {
              return {
                content: [
                  {
                    type: "text",
                    text: `Error: Guideline "${guideline}" not found.`,
                  },
                ],
                isError: true,
              };
            }
            files = [`${guideline}.xml`];
          } else {
            files = listGuidelineFiles();
          }

          const allRules = [];
          for (const file of files) {
            const filePath = path.join(GUIDELINES_DIR, file);
            const rules = extractRules(filePath, severity, section);
            if (rules.length > 0) {
              allRules.push({
                file: path.basename(file, ".xml"),
                rules,
              });
            }
          }

          if (allRules.length === 0) {
            const filters = [];
            if (severity) filters.push(`severity="${severity}"`);
            if (section) filters.push(`section="${section}"`);
            if (guideline) filters.push(`guideline="${guideline}"`);
            return {
              content: [
                {
                  type: "text",
                  text: `No rules found matching filters: ${filters.join(", ") || "none"}`,
                },
              ],
            };
          }

          const output = allRules
            .map((entry) => {
              const header = `=== ${entry.file} (${entry.rules.length} rules) ===`;
              const body = entry.rules
                .map((r) => {
                  let line = `  [${r.severity}] ${r.id}`;
                  if (r.enforcement) line += ` (enforcement: ${r.enforcement})`;
                  if (r.description) line += `\n    ${r.description}`;
                  if (r.constraints.length > 0) {
                    line += "\n    Constraints:";
                    for (const c of r.constraints) {
                      line += `\n      - ${c}`;
                    }
                  }
                  return line;
                })
                .join("\n");
              return `${header}\n${body}`;
            })
            .join("\n\n");

          const totalRules = allRules.reduce(
            (sum, e) => sum + e.rules.length,
            0
          );
          return {
            content: [
              {
                type: "text",
                text: `Found ${totalRules} rules across ${allRules.length} files:\n\n${output}`,
              },
            ],
          };
        }

        case "get_guideline_for_language": {
          const lang = args.language;
          if (!lang) {
            return {
              content: [
                { type: "text", text: "Error: 'language' parameter is required" },
              ],
              isError: true,
            };
          }

          const key = lang.toLowerCase().trim();
          const guidelineName = LANGUAGE_MAP[key];

          if (!guidelineName) {
            const supported = [
              ...new Set(Object.values(LANGUAGE_MAP)),
            ].sort();
            return {
              content: [
                {
                  type: "text",
                  text: `No guideline mapping found for "${lang}".\nSupported mappings: ${Object.keys(LANGUAGE_MAP).sort().join(", ")}\nGuideline files: ${supported.join(", ")}`,
                },
              ],
              isError: true,
            };
          }

          const filePath = path.join(GUIDELINES_DIR, `${guidelineName}.xml`);
          if (!fs.existsSync(filePath)) {
            return {
              content: [
                {
                  type: "text",
                  text: `Guideline file "${guidelineName}.xml" mapped from "${lang}" does not exist at ${filePath}`,
                },
              ],
              isError: true,
            };
          }

          const fileContent = fs.readFileSync(filePath, "utf-8");
          return {
            content: [
              {
                type: "text",
                text: `Guideline for "${lang}" (${guidelineName}.xml):\n\n${fileContent}`,
              },
            ],
          };
        }

        default:
          return {
            content: [
              { type: "text", text: `Unknown tool: ${name}` },
            ],
            isError: true,
          };
      }
    } catch (err) {
      return {
        content: [
          {
            type: "text",
            text: `Error executing tool "${name}": ${err.message}`,
          },
        ],
        isError: true,
      };
    }
  });

  // --- Resources ---
  server.setRequestHandler(ListResourcesRequestSchema, async () => {
    const files = listGuidelineFiles();
    const resources = files.map((f) => {
      const basename = path.basename(f, ".xml");
      return {
        uri: `guidelines://${basename}`,
        name: basename,
        mimeType: "application/xml",
        description: `Guideline: ${basename.replace(/_/g, " ")}`,
      };
    });

    return { resources };
  });

  server.setRequestHandler(ListResourceTemplatesRequestSchema, async () => {
    return {
      resourceTemplates: [
        {
          uriTemplate: "guidelines://{name}",
          name: "Guideline by name",
          mimeType: "application/xml",
          description:
            "Retrieve a guideline XML file by name (without .xml extension)",
        },
      ],
    };
  });

  server.setRequestHandler(ReadResourceRequestSchema, async (request) => {
    const uri = request.params.uri;

    if (uri === "guidelines://list") {
      const files = listGuidelineFiles();
      const metadata = files.map((f) =>
        parseGuidelineMetadata(path.join(GUIDELINES_DIR, f))
      );
      return {
        contents: [
          {
            uri,
            mimeType: "application/json",
            text: JSON.stringify(metadata, null, 2),
          },
        ],
      };
    }

    const uriMatch = uri.match(/^guidelines:\/\/(.+)$/);
    if (!uriMatch) {
      throw new Error(`Invalid resource URI: ${uri}`);
    }

    const resourceName = uriMatch[1];
    const filePath = path.join(GUIDELINES_DIR, `${resourceName}.xml`);

    if (!fs.existsSync(filePath)) {
      throw new Error(
        `Guideline "${resourceName}" not found at ${filePath}`
      );
    }

    const fileContent = fs.readFileSync(filePath, "utf-8");
    return {
      contents: [
        {
          uri,
          mimeType: "application/xml",
          text: fileContent,
        },
      ],
    };
  });

  const transport = new StdioServerTransport();
  await server.connect(transport);
  console.error("guidelines-retriever MCP server running on stdio");
}

main().catch((err) => {
  console.error("Fatal error:", err);
  process.exit(1);
});
