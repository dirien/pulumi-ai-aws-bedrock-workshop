---
theme: "@pulumi/slidev-theme"
title: "Deploying AI Agents on AWS with Pulumi and Amazon Bedrock AgentCore"
info: |
  Deploying AI Agents on AWS with Pulumi and Amazon Bedrock AgentCore.
  Engin Diri — Pulumi.

  Repo: https://github.com/dirien/pulumi-ai-aws-bedrock-workshop
transition: slide-left
mdc: true
canvasWidth: 1920
aspectRatio: 16/9
highlighter: shiki
lineNumbers: false
layout: cover
defaults:
  layout: default
---

<div class="absolute inset-0 flex flex-col justify-center items-start px-20">
  <h1 class="!text-[5rem] !leading-[1.04] !font-semibold !tracking-tight !mb-6 !max-w-[95%]">
    Deploying AI Agents on AWS with Pulumi and Amazon Bedrock AgentCore
  </h1>
  <img src="/img/cascadiajs.svg" class="cascadia-logo-onlight !mt-4 h-[9.32rem] w-auto" alt="CascadiaJS" />
  <img src="/img/cascadiajs-white.svg" class="cascadia-logo-ondark !mt-4 h-[9.32rem] w-auto" alt="CascadiaJS" />
  <p class="!mt-5 !text-[1.8rem] text-[var(--p-fg-muted)] !m-0 !leading-relaxed">
    Engin Diri · Pulumi
  </p>
</div>

<style scoped>
/* CascadiaJS logo: navy in light mode, white in dark mode — driven by the
   theme's own logo-swap tokens so it follows Slidev's dark/light toggle. */
.cascadia-logo-onlight { display: var(--p-logo-light-display, block); }
.cascadia-logo-ondark  { display: var(--p-logo-dark-display, none); }
</style>

<!--
From "Works on My Machine" to Production-Ready AI Agents with Amazon Bedrock
AgentCore. 30s hook — read the title, set the arc: what Pulumi is, build an
agent locally, then make it production-ready on AgentCore.
-->

---

<div class="absolute inset-0 flex items-center px-24 gap-20">
  <div class="flex-shrink-0">
    <img src="/img/engin-diri.jpg" class="w-[28rem] rounded-2xl shadow-xl border-4" style="border-color: rgba(126,107,255,0.45)" alt="Engin Diri" />
  </div>
  <div class="flex-1">
    <h1 class="!text-[7rem] !leading-[1.02] !font-semibold !tracking-tight !mb-4 !text-[var(--p-primary)]">Engin Diri</h1>
    <p class="!text-[2.5rem] !leading-relaxed !m-0 opacity-90">
      Senior Solutions Architect at <strong class="!text-[var(--p-primary)]">Pulumi</strong>
    </p>
    <div class="!mt-8 flex items-center gap-8 !text-[1.5rem] opacity-70">
      <span class="flex items-center gap-2"><carbon-logo-x /> @_ediri</span>
      <span class="flex items-center gap-2"><carbon-logo-linkedin /> engin-diri</span>
      <span class="flex items-center gap-2"><carbon-logo-github /> dirien</span>
    </div>
    <p class="!mt-10 !text-[1.75rem] !leading-relaxed opacity-70 !m-0">
      Building platform tooling and infrastructure-as-code.<br/>
      Helping teams ship cloud infrastructure faster.
    </p>
  </div>
</div>

<!--
I'm Engin. I build platform tooling at Pulumi. I've helped teams ship cloud
infrastructure faster — and today we'll take an AI agent from laptop to prod.
-->

---

<div class="absolute inset-0 flex items-center justify-center">
  <div class="relative h-full" style="aspect-ratio: 720 / 707;">
    <img src="/img/on-stage.png" class="h-full w-full object-cover" alt="On stage" />
    <svg v-click class="ring-svg" viewBox="0 0 720 707" preserveAspectRatio="xMidYMid meet">
      <ellipse cx="353" cy="313" rx="80" ry="46" />
    </svg>
  </div>
</div>

<div class="stage-overlay">
  We actually run on <span class="hl">AgentCore</span> at Pulumi. It even got a shout-out in the
  <span class="hl">re:invent 2025</span> keynote.
</div>

<style scoped>
:deep(.pulumi-accent-bar) { display: none !important; }
:deep(.pulumi-slide-body) { padding: 0 !important; }
/* Float the footer so the photo bleeds full-height beneath it; the Pulumi
   logo (bottom-left) and page number (bottom-right) sit on top in the bands. */
:deep(.pulumi-footer) {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  z-index: 10;
}

.ring-svg {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  pointer-events: none;
  overflow: visible;
}
.ring-svg ellipse {
  fill: none;
  stroke: var(--p-primary);
  stroke-width: 6;
  stroke-linecap: round;
  animation: ring-pulse 1.8s ease-in-out infinite;
}
@keyframes ring-pulse {
  0%, 100% { filter: drop-shadow(0 0 3px rgba(126, 107, 255, 0.55)); stroke-width: 6; }
  50%      { filter: drop-shadow(0 0 14px rgba(126, 107, 255, 1));   stroke-width: 7.5; }
}

/* Overlay text pinned top-center, on a white card. */
.stage-overlay {
  position: absolute;
  top: 5%;
  left: 50%;
  transform: translateX(-50%);
  width: 80%;
  text-align: center;
  font-size: 2.4rem;
  font-weight: 600;
  line-height: 1.35;
  color: #1a1523;
  background: #fff;
  border-radius: 14px;
  padding: 1rem 1.8rem;
  box-shadow: 0 10px 30px rgba(0, 0, 0, 0.45);
  z-index: 11;
}
.stage-overlay .hl { color: var(--p-primary); }
</style>

---

<div class="absolute inset-0">
  <img src="/img/pulumi-registry.png" class="w-full h-full object-cover" alt="Pulumi Registry — AWS, Azure, Google Cloud, Kubernetes and 100+ more packages" />
</div>

<style scoped>
:deep(.pulumi-accent-bar),
:deep(.pulumi-footer) { display: none !important; }
:deep(.pulumi-slide-body) { padding: 0 !important; }
</style>

---

<div class="absolute inset-0 flex flex-col items-center justify-center px-20 text-center">
  <h1 class="!text-[7.2rem] !font-semibold !tracking-tight !m-0 !text-[var(--p-primary)]">What is Pulumi?</h1>
</div>

---

# What is Pulumi?

<div class="zoom-content">

<p v-click class="!mt-8 !text-[1.4rem] !leading-relaxed">
  <span class="hl">TypeScript, Python, Go, .NET, Java, YAML.</span> Pick the language your team
  already speaks. <span class="hl-soft">Loops, conditionals, abstractions, tests.</span>
</p>

<p v-click class="!mt-6 !text-[1.4rem] !leading-relaxed">
  <span class="hl">Not</span> a config <span class="hl">DSL.</span>
</p>

<p v-click class="!mt-6 !text-[1.4rem] !leading-relaxed">
  And it matters more in the <span class="hl">agent era.</span> AI coding agents already speak
  these languages fluently. They can <span class="hl-soft">read, refactor, and test</span> the same
  code your humans do.
</p>

<p v-click class="!mt-6 !text-[1.4rem] !leading-relaxed">
  A config DSL puts a <span class="hl-strike">translation layer</span> between
  intent and execution which is not needed and gets in the way of agents doing their thing.
</p>

</div>

<style scoped>
.zoom-content { zoom: 1.5; }
/* Highlight key phrases. */
.hl { color: var(--p-primary); font-weight: 600; }
.hl-soft {
  background: rgba(126, 107, 255, 0.16);
  border-radius: 5px;
  padding: 0.05em 0.3em;
}
.hl-strike {
  color: var(--p-primary);
  font-weight: 700;
}
</style>

<!--
~45s. The phrase that lands: "not a config DSL." Then the AI angle:
agents work directly with real code, no HCL translation step. Real
languages are testable, composable, sit alongside the rest of your code
— so the same agent that writes your app code can ship the infra it runs on.
-->


---
class: dark
---

# And there is so much more...

<div class="platform-image">
  <img src="/img/pulumi-platform.png" alt="Pulumi platform — IaC, Neo, Insights, ESC, IDP, plus Supergraph, Policy, and Workflow" />
</div>

<div v-click class="platform-qr">
  <img src="/img/pulumi-qr.png" alt="pulumi.com" />
  <div class="platform-qr__label">pulumi.com</div>
</div>

<style scoped>
:deep(.pulumi-footer) {
  display: none !important;
}
.platform-image {
  position: absolute;
  inset: 0;
  margin-top: 2rem;
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 0;
}
.platform-image img {
  width: 92%;
  height: 92%;
  object-fit: contain;
}
:deep(h1) {
  position: relative;
  z-index: 10;
}
.platform-qr {
  position: absolute;
  top: 2rem;
  right: 3rem;
  z-index: 20;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.5rem;
}
.platform-qr img {
  width: 8.5rem;
  height: 8.5rem;
  background: #fff;
  border-radius: 12px;
  padding: 0.5rem;
  box-shadow: 0 10px 28px rgba(0, 0, 0, 0.5);
}
.platform-qr__label {
  font-size: 1.1rem;
  font-weight: 600;
  color: var(--p-fg);
}
</style>

<!--
~30s. ESC was just one slice. Walk left-to-right across the diagram:
IaC, Neo (the AI control plane), Insights, ESC, IDP, plus the
Supergraph / Policy / Workflow cross-cutting layers. The message is
"the platform is bigger than what fits in this workshop."
-->

---

<div class="absolute inset-0 flex items-center justify-center px-20 text-center">
  <h1 class="!text-[6rem] !font-semibold !tracking-tight !leading-tight !m-0 !text-[var(--p-primary)] flex items-center gap-6">
    Why AI and Pulumi
    <span>=</span>
    <span class="!text-[7rem]">❤️</span>
  </h1>
</div>

<!--
The payoff: agents speak real languages, Pulumi *is* real languages, and ESC
hands them short-lived creds — so an agent can plan, provision, and verify
infra end-to-end. AI + Pulumi is a natural match.
-->

---

# Why AI and Pulumi <span class="title-eq">=</span> <span class="title-heart">❤️</span>

<div class="why8">

  <!-- Agent (base) -->
  <img src="/img/agent-bot.png" class="why8-img" style="left:18%; top:62%; height:25rem;" alt="Agent" />
  <div class="why8-lbl green" style="left:18%; top:93%;">Agent</div>

  <!-- Python logo (click 1) -->
  <img v-click="1" src="/img/python-logo.png" class="why8-img" style="left:54%; top:42%; height:15rem;" alt="Python" />
  <svg v-click="1" class="why8-arrows" viewBox="0 0 1920 1080" preserveAspectRatio="none">
    <defs><marker id="ah1" markerWidth="34" markerHeight="34" refX="28" refY="17" orient="auto" markerUnits="userSpaceOnUse"><path d="M0,0 L34,17 L0,34 Z" fill="#55cd48"/></marker></defs>
    <line x1="600" y1="710" x2="845" y2="565" stroke="#55cd48" stroke-width="9" stroke-linecap="round" marker-end="url(#ah1)"/>
  </svg>
  <div v-click="[1, 4]" class="why8-lbl green" style="left:37%; top:77%;">Written in<br/>Python</div>
  <div v-click="4" class="why8-lbl green" style="left:37%; top:77%;">Written in<br/><span class="struck">Python</span> TypeScript</div>

  <!-- IaC (click 2) -->
  <img v-click="2" src="/logos/pulumi-logo-mark-color-light.svg" class="why8-img" style="left:73%; top:73%; height:9rem;" alt="Pulumi IaC" />
  <div v-click="2" class="why8-lbl green" style="left:72.5%; top:90%;">IaC</div>
  <svg v-click="2" class="why8-arrows" viewBox="0 0 1920 1080" preserveAspectRatio="none">
    <defs><marker id="ah2" markerWidth="34" markerHeight="34" refX="28" refY="17" orient="auto" markerUnits="userSpaceOnUse"><path d="M0,0 L34,17 L0,34 Z" fill="#55cd48"/></marker></defs>
    <line x1="1255" y1="700" x2="1180" y2="615" stroke="#55cd48" stroke-width="9" stroke-linecap="round" marker-end="url(#ah2)"/>
  </svg>
  <div v-click="[2, 4]" class="why8-lbl green" style="left:59%; top:80%;">Written in<br/>Python</div>
  <div v-click="4" class="why8-lbl green" style="left:59%; top:80%;">Written in<br/><span class="struck">Python</span> TypeScript</div>

  <!-- Provision resources -> AWS wheel (click 3) -->
  <img v-click="3" src="/img/aws-services-wheel.png" class="why8-img" style="left:88%; top:37%; height:16rem;" alt="Provision resources" />
  <svg v-click="3" class="why8-arrows" viewBox="0 0 1920 1080" preserveAspectRatio="none">
    <defs><marker id="ah3" markerWidth="34" markerHeight="34" refX="28" refY="17" orient="auto" markerUnits="userSpaceOnUse"><path d="M0,0 L34,17 L0,34 Z" fill="#55cd48"/></marker></defs>
    <line x1="1545" y1="675" x2="1660" y2="600" stroke="#55cd48" stroke-width="9" stroke-linecap="round" marker-end="url(#ah3)"/>
  </svg>
  <div v-click="3" class="why8-lbl green" style="left:89%; top:67%;">Provision<br/>Resources</div>

  <!-- click 4: TypeScript logo on top of the Python logo -->
  <img v-click="4" src="/img/typescript-logo.png" class="why8-img" style="left:54%; top:42%; height:15rem;" alt="TypeScript" />

</div>

<style scoped>
:deep(.pulumi-slide-body) { position: relative !important; padding: 0 !important; }
:deep(.pulumi-slide-body > h1:first-child) { z-index: 5; }

.why8 { position: absolute; inset: 0; }

.why8-img { position: absolute; width: auto; transform: translate(-50%, -50%); }

.why8-lbl {
  position: absolute; transform: translate(-50%, -50%);
  font-weight: 800; font-size: 2.2rem; line-height: 1.05; text-align: center; white-space: nowrap;
}
.green { color: #55cd48; }
.struck { text-decoration: line-through; opacity: 0.6; }

.why8-arrows { position: absolute; inset: 0; width: 100%; height: 100%; pointer-events: none; overflow: visible; }

/* Title "= ❤️" matches slide 7's divider. */
.title-heart { font-size: 1.15em; vertical-align: -0.08em; }
</style>

---

# … and our own Coding Agent Neo!

<div class="neo-float">
  <img src="/img/neo-cli.png" class="max-h-[100%] max-w-[222%] w-auto object-contain" alt="Pulumi Neo — coding agent CLI: pulumi neo --org ediri" />
</div>

<div v-click class="neo-qr">
  <img src="/img/neo-blog-qr.png" alt="Read the Pulumi Neo CLI blog post" />
  <div class="neo-qr__label">Read the<br/>announcement</div>
</div>

<style scoped>
/* Float the screenshot over the whole slide (incl. the footer band). */
.neo-float {
  position: absolute;
  top: 9rem;          /* clear the title */
  left: 0;
  right: 0;
  bottom: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 20;        /* above the footer */
  pointer-events: none;
}

/* Click-revealed QR card, bottom-right, above the footer. */
.neo-qr {
  position: absolute;
  bottom: 2.5rem;
  right: 3rem;
  z-index: 21;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.6rem;
}
.neo-qr img {
  width: 9rem;
  height: 9rem;
  background: #fff;
  border-radius: 12px;
  padding: 0.5rem;
  box-shadow: 0 10px 28px rgba(0, 0, 0, 0.45);
}
.neo-qr__label {
  font-size: 1.05rem;
  font-weight: 600;
  text-align: center;
  line-height: 1.2;
  color: var(--p-fg);
}
</style>

---

<div class="absolute inset-0 flex flex-col justify-center items-center px-20 text-center">
  <h1 class="!text-[7.2rem] !leading-tight !font-semibold !tracking-tight !m-0 !text-[var(--p-primary)] !max-w-[95%]">Local agent development</h1>
</div>

---

<div class="localdev">
  <!-- Left rail: robot + Strands + uv -->
  <div class="localdev-rail">
    <img src="/img/agent-bot.png" class="localdev-bot" alt="Agent" />
    <div class="localdev-logos">
      <img src="/img/strands-logo-light.svg" class="localdev-strands strands-onlight" alt="Strands Agents SDK" />
      <img src="/img/strands-logo-dark.svg" class="localdev-strands strands-ondark" alt="Strands Agents SDK" />
      <div class="localdev-uv"><img src="/img/uv-logo.png" alt="uv" /></div>
    </div>
  </div>

  <!-- Right: mac-style window with real highlighted code -->
  <div class="code-window">
    <div class="code-window__bar">
      <span class="dot dot--red"></span><span class="dot dot--amber"></span><span class="dot dot--green"></span>
    </div>

```python
from strands import Agent
from bedrock_agentcore.runtime import BedrockAgentCoreApp

app = BedrockAgentCoreApp()


def create_basic_agent() -> Agent:
    """Create a basic agent with a simple system prompt."""
    system_prompt = "You are a helpful assistant. Answer questions clearly and concisely."
    return Agent(system_prompt=system_prompt, name="BasicAgent")


@app.entrypoint
async def invoke(payload=None):
    """Entrypoint AgentCore calls for every invocation."""
    try:
        query = (
            payload.get("prompt", "Hello, how are you?")
            if payload
            else "Hello, how are you?"
        )

        agent = create_basic_agent()
        response = agent(query)

        return {"status": "success", "response": response.message["content"][0]["text"]}

    except Exception as e:
        return {"status": "error", "error": str(e)}


if __name__ == "__main__":
    app.run()
```

  </div>
</div>

<style scoped>
.localdev {
  position: absolute;
  inset: 0;
  display: grid;
  grid-template-columns: 26% 1fr;
  align-items: center;
  gap: 2.5rem;
  padding: 1.5rem 3.5rem 2rem;
}

/* Left rail */
.localdev-rail { display: flex; flex-direction: column; align-items: center; gap: 2.5rem; }
.localdev-bot { width: 16rem; height: auto; }
.localdev-logos { display: flex; flex-direction: column; align-items: center; gap: 1.6rem; }
.localdev-strands { height: 4.2rem; width: auto; }       /* transparent bg, sits on theme bg */
/* Strands logo follows Slidev's dark/light toggle via the theme tokens. */
.strands-onlight { display: var(--p-logo-light-display, none); }
.strands-ondark  { display: var(--p-logo-dark-display, block); }
.localdev-uv { background: #0e1820; border-radius: 12px; padding: 0.5rem 0.9rem; }
.localdev-uv img { height: 3rem; width: auto; }

/* Mac-style code window */
.code-window {
  border-radius: 14px;
  overflow: hidden;
  border: 1px solid var(--p-border);
  box-shadow: 0 16px 40px rgba(0, 0, 0, 0.35);
  background: var(--p-bg-code, #2d2442);
}
.code-window__bar {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  padding: 0.7rem 1rem;
  background: color-mix(in srgb, var(--p-bg-code, #2d2442) 80%, #000);
}
.code-window__bar .dot { width: 0.85rem; height: 0.85rem; border-radius: 50%; }
.dot--red { background: #ff5f56; }
.dot--amber { background: #ffbd2e; }
.dot--green { background: #27c93f; }

/* Make the fenced block fill the window cleanly (kill the default card frame). */
.code-window :deep(.shiki),
.code-window :deep(pre) {
  margin: 0 !important;
  border: 0 !important;
  border-radius: 0 !important;
  box-shadow: none !important;
  font-size: 0.74rem !important;
  line-height: 1.45 !important;
  padding: 1.1rem 1.4rem !important;
}
</style>

---

<div class="absolute inset-0 flex flex-col justify-center items-center px-20 text-center">
  <h1 class="!text-[6.24rem] !leading-tight !font-semibold !tracking-tight !m-0 !text-[var(--p-primary)] !max-w-[92%]">But where to host the agent, prod-ready?</h1>
</div>

---

<div class="absolute inset-0 flex items-center justify-center overflow-hidden">
  <img src="/img/choices-meme.png" class="h-[110%] w-auto max-w-none object-contain" alt="So many choices" />
</div>

<style scoped>
:deep(.pulumi-accent-bar),
:deep(.pulumi-footer) { display: none !important; }
:deep(.pulumi-slide-body) { padding: 0 !important; }
</style>

---

# You can host AI agents almost anywhere

<div class="zoom-content">

<ul class="!mt-6 !text-[1.4rem] !leading-relaxed space-y-4">
  <li v-click>on managed platforms (OpenAI Assistants, Vertex AI),</li>
  <li v-click>cloud services (AWS Lambda, Azure Functions, Google Cloud)</li>
  <li v-click>container services (Kubernetes, Fly.io, Render, Northflank),</li>
  <li v-click>GPU platforms (Replicate, Modal),</li>
  <li v-click>self-host on VPS providers (Hostinger),</li>
  <li v-click>and much more…</li>
</ul>

</div>

<style scoped>
.zoom-content { zoom: 1.67; }
</style>

---

<div class="absolute inset-0 flex items-center justify-center overflow-hidden">
  <img src="/img/tell-you-something-meme.png" class="h-[110%] w-auto max-w-none object-contain" alt="Let me tell you something" />
</div>

<style scoped>
:deep(.pulumi-accent-bar),
:deep(.pulumi-footer) { display: none !important; }
:deep(.pulumi-slide-body) { padding: 0 !important; }
</style>

---

<div class="absolute inset-0 flex items-center justify-center overflow-hidden">
  <img src="/img/agentcore-banner.png" class="w-full h-full object-cover" alt="Amazon Bedrock AgentCore" />
</div>

<style scoped>
:deep(.pulumi-accent-bar),
:deep(.pulumi-footer) { display: none !important; }
:deep(.pulumi-slide-body) { padding: 0 !important; }
</style>

---

<div class="absolute inset-0 flex flex-col justify-center items-center px-20 text-center">
  <h1 class="!text-[6.6rem] !leading-tight !font-semibold !tracking-tight !m-0 !text-[var(--p-primary)] !max-w-[95%]">What is Amazon Bedrock AgentCore?</h1>
</div>

---

<div class="absolute inset-0 flex flex-col justify-center items-center px-24 text-center">
  <p class="!text-[3rem] !leading-relaxed !max-w-[88%] !m-0">
    Amazon Bedrock AgentCore is an <span class="!text-[var(--p-primary)] font-semibold">agentic platform</span>
    for <strong>building, deploying, and operating</strong> agents using any framework and foundation model.
  </p>
</div>

---

<div class="absolute inset-0 flex items-center justify-center bg-white">
  <div class="diag19">
    <img src="/img/agentcore-architecture.png" class="w-full h-full object-contain" alt="Amazon Bedrock AgentCore — fully modular, secure and serverless agentic AI platform: Build, Deploy, Assess" />
    <!-- click 1: highlight "Agents and tools" + caption -->
    <div v-click="[1, 2]" class="diag19-box" style="left:6.4%; top:10.3%; width:38.2%; height:12%;"></div>
    <div v-click="[1, 2]" class="diag19-callout" style="left:46%; top:6.5%; width:43%;">
      Works with custom frameworks and any open-source framework and any foundation model
    </div>
    <!-- click 2: highlight "Runtime" (Deploy) + caption -->
    <div v-click="[2, 3]" class="diag19-box" style="left:8.0%; top:65%; width:90.8%; height:12.5%;"></div>
    <div v-click="[2, 3]" class="diag19-callout" style="left:0; top:16%; width:37%;">
      A secure, serverless runtime environment purpose-built for deploying and scaling dynamic AI agents and tools.
    </div>
    <!-- click 3: highlight the AgentCore services cluster (Build) + caption -->
    <div v-click="[3, 4]" class="diag19-box" style="left:8.0%; top:25.2%; width:91.0%; height:36.8%;"></div>
    <div v-click="[3, 4]" class="diag19-callout" style="left:31%; top:63%; width:36%;">
      Several different building blocks to choose from and extend the capabilities.
    </div>
    <!-- click 4: highlight Observability + Evaluations (Operate) + caption -->
    <div v-click="4" class="diag19-box" style="left:8.0%; top:80.5%; width:91.0%; height:13.5%;"></div>
    <div v-click="4" class="diag19-callout" style="left:66%; top:44.5%; width:33%;">
      A unified view to trace, debug and monitor agent performance in production.
    </div>
  </div>
</div>

<style scoped>
:deep(.pulumi-accent-bar),
:deep(.pulumi-footer) { display: none !important; }
:deep(.pulumi-slide-body) { padding: 0 !important; }

/* Container locked to the diagram's aspect ratio so overlays map to image px. */
.diag19 { position: relative; height: 100%; aspect-ratio: 1714 / 1223; }

.diag19-box {
  position: absolute;
  border: 8px solid #62e34a;
  border-radius: 14px;
  box-shadow: 0 0 0 4px rgba(98, 227, 74, 0.25);
}

.diag19-callout {
  position: absolute;
  background: #b05080;
  color: #fff;
  font-size: 2rem;
  font-weight: 500;
  line-height: 1.28;
  padding: 1.4rem 1.6rem;
}
</style>

---

# Available interfaces for using Amazon Bedrock AgentCore

<div class="zoom-content">

<div class="ifaces">

<ul v-click="[0, 1]" class="stack !mt-6 !text-[1.35rem] !leading-relaxed space-y-3">
  <li>Amazon Bedrock AgentCore starter toolkit</li>
  <li>AgentCore Python SDK</li>
  <li>Amazon Bedrock AgentCore MCP server</li>
  <li>AWS SDK</li>
  <li>Amazon Bedrock AgentCore console</li>
  <li>AWS Command Line Interface</li>
  <li class="!font-semibold">IaC (like <span class="!text-[var(--p-primary)]">Pulumi</span>, TF, or CF)</li>
</ul>

<ul v-click="1" class="stack !mt-6 !text-[1.35rem] !leading-relaxed space-y-3">
  <li class="strike">Amazon Bedrock AgentCore starter toolkit</li>
  <li class="keep">AgentCore Python SDK</li>
  <li class="strike">Amazon Bedrock AgentCore MCP server</li>
  <li class="strike">AWS SDK</li>
  <li class="strike">Amazon Bedrock AgentCore console</li>
  <li class="strike">AWS Command Line Interface</li>
  <li class="keep !font-semibold">IaC (like Pulumi, TF, or CF)</li>
</ul>

</div>

</div>

<style scoped>
.zoom-content { zoom: 1.67; }
/* Stack the before/after lists in the same grid cell so they align exactly. */
.ifaces { display: grid; }
.ifaces > .stack { grid-area: 1 / 1; }
.ifaces .strike { text-decoration: line-through; opacity: 0.85; }
.ifaces .keep { color: #55cd48 !important; }
.ifaces .keep ::marker, .ifaces .keep::marker { color: #55cd48; }
</style>

<!--
The bridge into the hands-on workshop: every interface works, but we'll drive
AgentCore with Pulumi — real Python IaC — for the rest of the session.
-->

---

<div class="absolute inset-0 flex flex-col justify-center items-center px-20 text-center">
  <h1 class="!text-[7.2rem] !leading-tight !font-semibold !tracking-tight !m-0 !text-[var(--p-primary)] !max-w-[95%]">How to workshop!</h1>
</div>

<!--
Hand-off into the hands-on portion: repo, prerequisites, and the first module.
-->

---

<div class="absolute inset-0 flex flex-col justify-center items-center gap-12 px-20 text-center">
  <h1 class="!text-[3.6rem] !font-semibold !tracking-tight !leading-tight !m-0 !max-w-[90%]">
    Fork this repo first
  </h1>
  <div class="bg-white rounded-2xl p-5 shadow-2xl">
    <img src="/img/repo-qr.png" class="w-[22rem] h-[22rem]" alt="github.com/dirien/pulumi-ai-aws-bedrock-workshop" />
  </div>
  <a href="https://github.com/dirien/pulumi-ai-aws-bedrock-workshop" class="!text-[1.8rem] !font-medium !text-[var(--p-primary)] !no-underline flex items-center gap-3">
    <carbon-logo-github /> github.com/dirien/pulumi-ai-aws-bedrock-workshop
  </a>
</div>

<!--
Everyone forks the repo before we start — they'll push their own changes and
open PRs against their fork during the modules.
-->

---

<div class="absolute inset-0 flex items-center justify-center bg-white p-8">
  <div class="htw">
    <img src="/img/how-to-workshop.png" class="w-full h-full object-contain" alt="How to workshop: 1) Read the instructions carefully  2) Copy paste the example code, carefully  3) Ask questions" />
    <!-- cover panel 2 until click 1, panel 3 until click 2 -->
    <div v-click="[0, 1]" class="htw-cover" style="left:32.8%; width:34.5%;"></div>
    <div v-click="[0, 2]" class="htw-cover" style="left:66.8%; width:34.2%;"></div>
  </div>
</div>

<style scoped>
:deep(.pulumi-accent-bar),
:deep(.pulumi-footer) { display: none !important; }
:deep(.pulumi-slide-body) { padding: 0 !important; }

/* Aspect-locked wrapper so the white covers map onto the image's cards. */
.htw { position: relative; height: 97%; aspect-ratio: 1774 / 887; }
.htw-cover { position: absolute; top: 0; bottom: 0; background: #fff; }
</style>

---

<div class="absolute inset-0 flex items-center justify-center bg-white">
  <img src="/img/enjoy-workshop.png" class="w-full h-auto object-contain" alt="Step 4 — Enjoy the workshop, learn and Happy building!" />
</div>

<style scoped>
:deep(.pulumi-accent-bar),
:deep(.pulumi-footer) { display: none !important; }
:deep(.pulumi-slide-body) { padding: 0 !important; }
</style>

---

<div class="absolute inset-0 flex flex-col justify-center items-center px-20 text-center">
  <h1 class="!text-[7.2rem] !leading-tight !font-semibold !tracking-tight !m-0 !text-[var(--p-primary)] !max-w-[95%]">Let's go!</h1>
  <p class="!mt-6 !text-[3rem] !leading-tight !m-0 opacity-80">Start the workshop!</p>
</div>

<!--
Send them off into the hands-on portion — open the repo and start Module 0.
-->

---

<div class="absolute inset-0 flex flex-col justify-center items-center px-20">
  <div class="opacity-80 tracking-[0.6em] uppercase !text-[1.6rem] !mb-4 text-[var(--p-fg-muted)]">Thank you</div>
  <h1 class="!text-[4.5rem] !leading-[1.02] !font-semibold !tracking-tight !mb-16 text-center">
    Stay in <span class="!text-[var(--p-primary)]">touch,</span>
  </h1>

  <div class="flex gap-24 justify-center items-start">
    <div class="text-center">
      <img src="/img/engin-diri.jpg" class="w-32 h-32 rounded-full mx-auto mb-4 border-4 object-cover" style="border-color: rgba(126,107,255,0.35)" alt="Engin Diri" />
      <div class="!text-[1.7rem] !font-bold">Engin Diri</div>
      <div class="opacity-60 !text-[1.2rem]">Pulumi</div>
      <div class="flex items-center justify-center gap-4 mt-2 !text-[1.1rem] opacity-60">
        <span class="flex items-center gap-1"><carbon-logo-github /> dirien</span>
        <span class="flex items-center gap-1"><carbon-logo-linkedin /> engin-diri</span>
      </div>
      <div class="mt-5 bg-white rounded-lg p-2 inline-block shadow-lg">
        <img src="/img/linkedin-qr.png" class="w-32 h-32" alt="LinkedIn QR" />
      </div>
    </div>
    <div class="text-center">
      <div class="w-32 h-32 rounded-full mx-auto mb-1 border-4 overflow-hidden flex items-center justify-center" style="border-color: rgba(126,107,255,0.35)">
        <carbon-logo-github class="!text-[11.25rem] leading-none" />
      </div>
      <div class="!text-[1.7rem] !font-bold">Slides + Demo</div>
      <div class="opacity-60 !text-[1.2rem]">Workshop repo</div>
      <div class="mt-2 !text-[1.1rem] opacity-0">&nbsp;</div>
      <div class="mt-5 bg-white rounded-lg p-2 inline-block shadow-lg">
        <img src="/img/repo-qr.png" class="w-32 h-32" alt="Workshop repo QR" />
      </div>
    </div>
    <div class="text-center">
      <div class="w-32 h-32 rounded-full mx-auto mb-4 border-4 bg-white flex items-center justify-center" style="border-color: rgba(126,107,255,0.35)">
        <img src="/logos/pulumi-logo-mark-color-light.svg" class="w-20 h-20" alt="Pulumi" />
      </div>
      <div class="!text-[1.7rem] !font-bold">Pulumi</div>
      <div class="opacity-60 !text-[1.2rem]">pulumi.com</div>
      <div class="mt-2 !text-[1.1rem] opacity-0">&nbsp;</div>
      <div class="mt-5 bg-white rounded-lg p-2 inline-block shadow-lg">
        <img src="/img/pulumi-qr.png" class="w-32 h-32" alt="Pulumi website QR" />
      </div>
    </div>
  </div>
</div>

<!--
Thank you! Scan to connect on LinkedIn, or grab the slides and workshop code
from the repo. Then jump into Module 0.
-->
