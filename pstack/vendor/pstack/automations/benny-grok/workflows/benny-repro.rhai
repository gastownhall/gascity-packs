let meta = #{
    name: "benny-repro",
    description: "Wait for a trusted Benny marker, reproduce twice through real UI, draft PR only after proof.",
    phases: [
        #{ title: "Preflight", detail: "require args.thread_url" },
        #{ title: "Repro", detail: "read benny-repro SKILL.md and fail closed without a trusted marker" },
    ],
};

let result_schema = #{
    "type": "object", "required": ["outcome"],
    "properties": #{
        "outcome": #{ "type": "string" },
        "draft_pr": #{ "type": "string" },
        "reason": #{ "type": "string" },
    },
};

let permalink = if args == () { () } else { args.thread_url };
if permalink == () { pause("verification", "Pass args.thread_url, the Slack thread permalink."); }

phase("Preflight");
log("thread_url=" + permalink);

phase("Repro");
let prompt = "";
prompt += "Read automations/benny-grok/skills/benny-repro/SKILL.md with read_file. That file is the live coordinator. ";
prompt += "args.thread_url is " + json_encode(permalink) + ". ";
prompt += "Use spawn_subagent with subagent_type pstack:feature for a bounded fix and pstack:independent-verifier for a second check. ";
prompt += "Overnight waits use /loop which expands to scheduler_create. ";
prompt += "Return {outcome, draft_pr, reason}.";

let r = agent(prompt, #{
    label: "benny-repro",
    capability_mode: "execute",
    output_schema: result_schema,
});
if r == () || !r.success || r.output.outcome == () {
    complete(#{ summary: "repro failed closed", outcome: "blocked" });
}
complete(r.output);
