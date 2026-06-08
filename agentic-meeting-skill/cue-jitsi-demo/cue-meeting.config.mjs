import {
  CueHarness,
  KeywordCue,
  MappedActionTool,
  PunctuationCue,
  SpeakerChangedCue,
  TextCue,
  Triggers
} from "/home/amiller/projects/cue/packages/core/dist/index.js";

const PORT = Number(process.env.CUE_MEETING_PORT ?? 8798);

const TOOLS = {
  decision: "meeting.capture_decision",
  actionItem: "meeting.capture_action_item",
  redaction: "meeting.flag_redaction_request",
  claim: "meeting.flag_unverified_claim",
  route: "meeting.route_artifact"
};

class HeuristicMeetingProvider {
  infer({ observation, tools }) {
    if (observation.type !== "transcript.segment") {
      return pass("Not a transcript segment.");
    }

    const text = String(observation.payload.text ?? "").trim();
    if (!text) return pass("Empty transcript segment.");

    const available = new Set(tools.map((tool) => tool.name));
    const lower = text.toLowerCase();
    const speaker = String(observation.payload.speaker ?? "");

    if (available.has(TOOLS.redaction) && redactionRequested(lower)) {
      return [{
        tool: TOOLS.redaction,
        arguments: {
          quote: text,
          speaker,
          reason: inferRedactionReason(lower),
          scope: inferRedactionScope(lower)
        },
        confidence: 0.92
      }];
    }

    if (available.has(TOOLS.decision) && decisionCaptured(lower)) {
      return [{
        tool: TOOLS.decision,
        arguments: {
          decision: stripLeadIn(text),
          quote: text,
          speaker
        },
        confidence: 0.82
      }];
    }

    if (available.has(TOOLS.actionItem) && actionItemCaptured(lower)) {
      return [{
        tool: TOOLS.actionItem,
        arguments: {
          task: stripLeadIn(text),
          owner: inferOwner(text, speaker),
          due: inferDue(text),
          quote: text
        },
        confidence: 0.78
      }];
    }

    if (available.has(TOOLS.route) && routingRequested(lower)) {
      return [{
        tool: TOOLS.route,
        arguments: {
          quote: text,
          recipients: inferRecipients(text),
          artifactType: "followup_excerpt",
          reason: "Speaker requested a routed follow-up artifact."
        },
        confidence: 0.76
      }];
    }

    if (available.has(TOOLS.claim) && unverifiedClaim(lower)) {
      return [{
        tool: TOOLS.claim,
        arguments: {
          severity: "high",
          quote: text,
          reason: "The statement is absolute, underspecified, or asks for source checking.",
          suggestedFollowup: "Can we confirm the source, timeframe, denominator, and assumptions?"
        },
        confidence: 0.84
      }];
    }

    return pass("No high-confidence meeting action.");
  }
}

function pass(reason) {
  return [{ tool: "observe.pass", arguments: { reason } }];
}

function redactionRequested(lower) {
  return [
    "off the record",
    "don't put this in the notes",
    "do not put this in the notes",
    "keep this out of the notes",
    "keep this between us",
    "between us",
    "let's redact",
    "lets redact",
    "strike that",
    "confidential"
  ].some((pattern) => lower.includes(pattern));
}

function inferRedactionReason(lower) {
  if (lower.includes("off the record")) return "off_the_record";
  if (lower.includes("confidential")) return "confidential";
  if (lower.includes("between us")) return "limited_audience";
  return "speaker_requested";
}

function inferRedactionScope(lower) {
  if (lower.includes("public")) return "public";
  if (lower.includes("outside")) return "external";
  return "default_followup";
}

function decisionCaptured(lower) {
  return [
    "we decided",
    "decision is",
    "the decision is",
    "we agreed",
    "let's go with",
    "lets go with"
  ].some((pattern) => lower.includes(pattern));
}

function actionItemCaptured(lower) {
  return [
    "i'll take",
    "i will take",
    "i can take",
    "alice owns",
    "bob owns",
    "owner is",
    "due by",
    "by friday",
    "by tomorrow",
    "follow up"
  ].some((pattern) => lower.includes(pattern));
}

function routingRequested(lower) {
  return [
    "send this to",
    "share this with",
    "ops needs",
    "legal needs",
    "for the team",
    "public version",
    "participant version"
  ].some((pattern) => lower.includes(pattern));
}

function unverifiedClaim(lower) {
  return [
    "basically zero",
    "everyone agrees",
    "guaranteed",
    "no risk",
    "obviously true",
    "definitely impossible"
  ].some((pattern) => lower.includes(pattern));
}

function stripLeadIn(text) {
  return text
    .replace(/^\s*(we decided|the decision is|decision is|we agreed|let'?s go with)\s*/i, "")
    .trim();
}

function inferOwner(text, fallbackSpeaker) {
  const ownerMatch = text.match(/\b([A-Z][a-z]+)\s+owns\b/);
  if (ownerMatch) return ownerMatch[1];
  if (/\bI('ll| will| can)\s+take\b/i.test(text)) return fallbackSpeaker || "speaker";
  return "";
}

function inferDue(text) {
  const dueMatch = text.match(/\bby\s+([A-Za-z]+(?:day)?|tomorrow|next week|\d{1,2}\/\d{1,2})\b/i);
  return dueMatch ? dueMatch[0] : "";
}

function inferRecipients(text) {
  const match = text.match(/\b(?:send this to|share this with)\s+([^,.]+)/i);
  if (match) return match[1].split(/\s+and\s+|,\s*/).map((item) => item.trim()).filter(Boolean);
  if (/ops needs/i.test(text)) return ["ops"];
  if (/legal needs/i.test(text)) return ["legal"];
  if (/team/i.test(text)) return ["team"];
  return [];
}

function decisionTool() {
  return new MappedActionTool({
    name: TOOLS.decision,
    description: "Capture a meeting decision when the transcript contains an explicit decision or agreement.",
    cooldownSeconds: 8,
    inputSchema: {
      type: "object",
      properties: {
        decision: { type: "string" },
        quote: { type: "string" },
        speaker: { type: "string" }
      },
      required: ["decision", "quote"]
    },
    mapper: (call, context) => [{
      type: "meeting.decision_captured",
      payload: {
        ...call.arguments,
        sessionId: context.sessionId,
        confidence: call.confidence,
        observationId: context.observation.id
      }
    }]
  });
}

function actionItemTool() {
  return new MappedActionTool({
    name: TOOLS.actionItem,
    description: "Capture an accepted or likely accepted action item with owner and due date when available.",
    cooldownSeconds: 8,
    inputSchema: {
      type: "object",
      properties: {
        task: { type: "string" },
        owner: { type: "string" },
        due: { type: "string" },
        quote: { type: "string" }
      },
      required: ["task", "quote"]
    },
    mapper: (call, context) => [{
      type: "meeting.action_item_captured",
      payload: {
        ...call.arguments,
        sessionId: context.sessionId,
        confidence: call.confidence,
        observationId: context.observation.id
      }
    }]
  });
}

function redactionTool() {
  return new MappedActionTool({
    name: TOOLS.redaction,
    description: "Create a redaction policy event when a speaker asks to strike, redact, or limit sharing.",
    cooldownSeconds: 4,
    inputSchema: {
      type: "object",
      properties: {
        quote: { type: "string" },
        speaker: { type: "string" },
        reason: { type: "string" },
        scope: { type: "string" }
      },
      required: ["quote", "reason"]
    },
    mapper: (call, context) => [{
      type: "meeting.redaction_requested",
      payload: {
        ...call.arguments,
        sessionId: context.sessionId,
        confidence: call.confidence,
        observationId: context.observation.id
      }
    }]
  });
}

function claimTool() {
  return new MappedActionTool({
    name: TOOLS.claim,
    description: "Flag only concrete factual, metric, consensus, or risk claims that need immediate source checking.",
    cooldownSeconds: 60,
    inputSchema: {
      type: "object",
      properties: {
        severity: { type: "string", enum: ["medium", "high"] },
        quote: { type: "string" },
        reason: { type: "string" },
        suggestedFollowup: { type: "string" }
      },
      required: ["severity", "quote", "reason"]
    },
    mapper: (call, context) => [{
      type: "meeting.unverified_claim_flagged",
      payload: {
        ...call.arguments,
        sessionId: context.sessionId,
        confidence: call.confidence,
        observationId: context.observation.id
      }
    }]
  });
}

function routeTool() {
  return new MappedActionTool({
    name: TOOLS.route,
    description: "Capture an explicit request to route a meeting excerpt or follow-up artifact to a recipient group.",
    cooldownSeconds: 10,
    inputSchema: {
      type: "object",
      properties: {
        quote: { type: "string" },
        recipients: { type: "array", items: { type: "string" } },
        artifactType: { type: "string" },
        reason: { type: "string" }
      },
      required: ["quote", "recipients", "artifactType"]
    },
    mapper: (call, context) => [{
      type: "meeting.routing_requested",
      payload: {
        ...call.arguments,
        sessionId: context.sessionId,
        confidence: call.confidence,
        observationId: context.observation.id
      }
    }]
  });
}

export default {
  port: PORT,
  outputs: [
    { id: "meeting_actions", kind: "action", label: "Meeting actions", event: "action" },
    { id: "transcript", kind: "text", label: "Transcript", event: "transcript" }
  ],
  workflowManifest: {
    id: "jitsi-hermes-meeting-cue-demo",
    label: "Jitsi/Hermes Meeting Cue Demo",
    description: "Turns transcript.segment observations into conservative meeting actions."
  },
  createHarness({ sessionId }) {
    const provider = new HeuristicMeetingProvider();
    return new CueHarness({
      sessionId,
      cues: [
        new TextCue(["off the record", "let's redact", "strike that", "confidential"], { cooldownSeconds: 2 }),
        new KeywordCue(["decided", "agreed", "owns", "due by", "send this to", "share this with"], { cooldownSeconds: 2 }),
        new SpeakerChangedCue(),
        new PunctuationCue()
      ],
      programs: [
        {
          name: "meeting-live-artifact-capture",
          llmProvider: provider,
          allowedTools: Object.values(TOOLS),
          activationPolicy: { mode: "coalesce", scope: "observation", priority: ["text", "keyword", "speaker_changed", "punctuation"] },
          triggers: [
            Triggers.onCue("text"),
            Triggers.onCue("keyword"),
            Triggers.onCue("speaker_changed"),
            Triggers.onCue("punctuation")
          ]
        }
      ],
      tools: [
        decisionTool(),
        actionItemTool(),
        redactionTool(),
        claimTool(),
        routeTool()
      ]
    });
  },
  onAction(action, context) {
    console.log(`[meeting:${context.sessionId}] ${JSON.stringify(action)}`);
  }
};

