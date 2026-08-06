import { Link } from 'react-router-dom'

const SECTIONS = [
  {
    title: '1. Acceptance of Terms',
    body: 'By creating an account or using AgentOS Studio ("the Service"), you agree to these Terms of Service. If you are using the Service on behalf of an organization, you agree to these terms on that organization\'s behalf. If you do not agree, do not use the Service.',
  },
  {
    title: '2. The Service',
    body: 'AgentOS Studio is a platform for designing, building, testing, and running agentic AI systems: agents, workflows, prompts, tools, memory, and MCP gateway configurations. The Service may integrate with third-party AI providers (OpenAI, Anthropic, Google, and others). You are responsible for supplying your own API credentials for those providers, and for complying with each provider\'s terms of service and usage policies.',
  },
  {
    title: '3. Accounts',
    body: 'You must provide accurate information when creating an account and keep your credentials secure. You are responsible for all activity that occurs under your account, including activity by API keys you create. Notify us immediately if you suspect unauthorized use. You may not create accounts for the purpose of circumventing usage limits or restrictions.',
  },
  {
    title: '4. Acceptable Use',
    body: 'You agree not to: (a) use the Service to violate any law or regulation; (b) build, deploy, or run agents that generate unlawful, harmful, or deceptive content; (c) attempt to gain unauthorized access to the Service, its infrastructure, or other users\' data; (d) reverse-engineer, scrape, or resell the Service; (e) interfere with or disrupt the Service, including through automated abuse or denial-of-service activity; or (f) store or process data you lack the right to store or process.',
  },
  {
    title: '5. Your Content',
    body: 'You retain all rights to the content, prompts, agents, workflows, and data you store in the Service ("Your Content"). By using the Service, you grant us a limited license to host, process, and transmit Your Content solely to operate and improve the Service. We do not sell Your Content, and we do not train models on it without your explicit consent.',
  },
  {
    title: '6. Third-Party Providers & AI Output',
    body: 'The Service acts as an intermediary between you and third-party AI providers. We do not control the output of those models and make no guarantees about its accuracy, safety, or suitability. AI output may be incorrect, biased, or harmful — you are responsible for reviewing and validating any output before relying on it. Provider outages or policy changes may affect availability.',
  },
  {
    title: '7. API Keys & Secrets',
    body: 'Credentials you store in the Service are encrypted at rest and treated as confidential. You are responsible for the security of your own API keys and for any costs incurred by their use. Remove or rotate keys promptly if they are compromised.',
  },
  {
    title: '8. Fees & Plans',
    body: 'The Service may be offered free of charge or under paid plans. If you subscribe to a paid plan, fees are billed in advance and are non-refundable except as required by law. We may change pricing with reasonable notice; price changes do not affect your current billing period unless you renew.',
  },
  {
    title: '9. Termination',
    body: 'You may delete your account at any time from your profile settings. We may suspend or terminate access if you violate these Terms, if required by law, or to protect the Service and its users. Upon termination, your right to use the Service ends; you may export your data before deletion as described in our Privacy Policy.',
  },
  {
    title: '10. Disclaimers',
    body: 'THE SERVICE IS PROVIDED "AS IS" AND "AS AVAILABLE," WITHOUT WARRANTIES OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE, AND NON-INFRINGEMENT. WE DO NOT WARRANT THAT THE SERVICE WILL BE UNINTERRUPTED, ERROR-FREE, OR SECURE.',
  },
  {
    title: '11. Limitation of Liability',
    body: 'TO THE MAXIMUM EXTENT PERMITTED BY LAW, NEITHER WE NOR OUR AFFILIATES SHALL BE LIABLE FOR ANY INDIRECT, INCIDENTAL, SPECIAL, CONSEQUENTIAL, OR PUNITIVE DAMAGES, OR ANY LOSS OF PROFITS, REVENUE, DATA, OR GOODWILL, ARISING OUT OF OR RELATED TO YOUR USE OF THE SERVICE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGES. OUR TOTAL LIABILITY FOR ALL CLAIMS SHALL NOT EXCEED THE GREATER OF (A) THE AMOUNT YOU PAID US IN THE TWELVE MONTHS PRECEDING THE CLAIM, OR (B) ONE HUNDRED DOLLARS.',
  },
  {
    title: '12. Changes to These Terms',
    body: 'We may update these Terms from time to time. Material changes will be announced in the Service or by email. Continued use of the Service after changes take effect constitutes acceptance of the revised Terms.',
  },
  {
    title: '13. Governing Law',
    body: 'These Terms are governed by the laws of the jurisdiction in which the Service operator is established, without regard to conflict-of-law principles. You agree to resolve any disputes through the courts of that jurisdiction.',
  },
  {
    title: '14. Contact',
    body: 'Questions about these Terms may be sent to the support email listed on the Service. We aim to respond within a reasonable time.',
  },
]

export default function Terms() {
  return (
    <div className="min-h-screen bg-surface-950 text-surface-100">
      <div className="max-w-3xl mx-auto px-6 py-16">
        <Link to="/" className="text-sm text-primary-400 hover:text-primary-300 transition-colors">
          ← Back to AgentOS
        </Link>
        <h1 className="text-4xl font-light tracking-tight serif-display mt-6">Terms of Service</h1>
        <p className="text-surface-400 text-sm mt-2">Last updated: August 2026</p>
        <p className="text-surface-400 mt-6 leading-relaxed">
          These Terms of Service ("Terms") govern your access to and use of AgentOS Studio. Please read them carefully.
        </p>
        <div className="mt-8 space-y-8">
          {SECTIONS.map((s) => (
            <section key={s.title}>
              <h2 className="text-lg font-semibold text-surface-100">{s.title}</h2>
              <p className="text-surface-300/90 leading-relaxed mt-2 text-sm">{s.body}</p>
            </section>
          ))}
        </div>
        <div className="mt-12 pt-6 border-t border-surface-800 text-sm text-surface-500">
          <Link to="/privacy" className="text-primary-400 hover:text-primary-300 transition-colors">
            Read the Privacy Policy →
          </Link>
        </div>
      </div>
    </div>
  )
}
