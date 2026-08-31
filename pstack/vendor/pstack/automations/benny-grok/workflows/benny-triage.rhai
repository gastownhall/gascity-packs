let meta = #{
    name: "benny-triage",
    description: "Triage one Slack report. One thread-only verdict with a Benny marker.",
    phases: [
        #{ title: "Preflight", detail: "require args.thread_url" },
        #{ title: "Triage", detail: "read benny-triage SKILL.md and post one marker" },
    ],
};

let verdict_schema = #{
    "type": "object", "required": ["marker", "posted_in_thread"],
    "properties": #{
        "marker": #{ "type": "string" },
        "posted_in_thread": #{ "type": "boolean" },
        "tracker": #{ "type": "string" },
        "reason": #{ "type": "string" },
    },
};

let permalink = if args == () { () } else { args.thread_url };
if permalink == () { pause("verification", "Pass args.thread_url, the Slack thread permalink."); }

phase("Preflight");
log("thread_url=" + permalink);

phase("Triage");
let prompt = "";
prompt += "Read automations/benny-grok/skills/benny-triage/SKILL.md with read_file. That file is the live coordinator. ";
prompt += "args.thread_url is " + json_encode(permalink) + ". ";
prompt += "Use spawn_subagent with subagent_type pstack:how-explorer for cause. ";
prompt += "Overnight waits use /loop which expands to scheduler_create. ";
prompt += "Return {marker, posted_in_thread, tracker, reason}.";

let r = agent(prompt, #{
    label: "benny-triage",
    capability_mode: "execute",
    output_schema: verdict_schema,
});
if r == () || !r.success || r.output.marker == () {
    complete(#{ summary: "triage failed closed", posted_in_thread: false });
}
complete(r.output);
