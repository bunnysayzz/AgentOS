import { Link } from 'react-router-dom'

const SECTIONS = [
  {
    title: '1. Who We Are',
    body: 'AgentOS Studio ("we", "us", "our") operates the AgentOS Studio platform for building and running agentic AI systems. This Privacy Policy explains what data we collect, why we collect it, and the choices you have.',
  },
  {
    title: '2. Data We Collect',
    body: 'Account data: your name, email address, username, and (if you sign in with Google) your profile picture. Content you create: workspaces, agents, workflows, prompts, tools, secrets, memory entries, artifacts, execution logs, and telemetry events. Usage data: pages visited, features used, and aggregate metrics. Technical data: IP address, browser type, and device information, collected for security and reliability.',
  },
  {
    title: '3. Authentication',
    body: 'We use Firebase Authentication for sign-in. If you register with email and password, Firebase stores a hashed credential on our behalf. If you sign in with Google, Google shares your name, email, and profile picture with us. We never see or store your password.',
  },
  {
    title: '4. How We Use Your Data',
    body: 'We use your data to provide and operate the Service, to authenticate you, to store your content, to route requests to AI providers you configure, to prevent abuse and security incidents, to improve the Service, and to communicate with you about your account.',
  },
  {
    title: '5. Third-Party AI Providers',
    body: 'When you configure an AI provider (OpenAI, Anthropic, Google, etc.), prompts and content you send are transmitted to that provider to generate responses. Each provider processes that data under its own privacy policy and terms. You are responsible for configuring providers that meet your compliance needs, and for not sending sensitive data to providers you do not trust.',
  },
  {
    title: '6. Storage & Security',
    body: 'Your data is stored in Google Cloud Firestore and Firebase Storage. Secrets and API keys are encrypted at rest. Access to the Service is authenticated, and our security rules deny direct client access to the database. No system is perfectly secure; we cannot guarantee absolute security.',
  },
  {
    title: '7. Data Retention',
    body: 'We retain your data while your account is active. You may delete individual items at any time. When you delete your account, we permanently remove your profile and the content associated with it within a reasonable period, except where we are required to retain data by law or for legitimate security purposes (such as logs needed to investigate abuse).',
  },
  {
    title: '8. Your Rights (GDPR & CCPA)',
    body: 'Depending on your jurisdiction, you may have the right to access, correct, export, and delete your personal data, and to object to or restrict certain processing. You can exercise most of these directly in the Service: edit your profile, export your data, and delete your account from Settings. For anything else, contact us and we will respond within the timeframe required by law.',
  },
  {
    title: '9. Cookies & Analytics',
    body: 'The Service uses only essential cookies/local storage required for authentication and session persistence. If we deploy optional analytics, it is privacy-respecting and does not track you across unrelated sites. You can block non-essential analytics in your browser settings.',
  },
  {
    title: '10. Children',
    body: 'The Service is not directed at children under 13 (or the applicable minimum age in your jurisdiction). We do not knowingly collect personal data from children. If you believe a child has provided us data, contact us and we will delete it.',
  },
  {
    title: '11. Changes to This Policy',
    body: 'We may update this Privacy Policy as the Service evolves. Material changes will be announced in the Service or by email. Continued use after changes take effect constitutes acceptance.',
  },
  {
    title: '12. Contact & Complaints',
    body: 'For privacy questions or requests, contact the support email listed on the Service. If you are in the EU/EEA, you also have the right to lodge a complaint with your local data protection authority.',
  },
]

export default function Privacy() {
  return (
    <div className="min-h-screen bg-surface-950 text-surface-100">
      <div className="max-w-3xl mx-auto px-6 py-16">
        <Link to="/" className="text-sm text-primary-400 hover:text-primary-300 transition-colors">
          ← Back to AgentOS
        </Link>
        <h1 className="text-4xl font-light tracking-tight serif-display mt-6">Privacy Policy</h1>
        <p className="text-surface-400 text-sm mt-2">Last updated: August 2026</p>
        <p className="text-surface-400 mt-6 leading-relaxed">
          This Privacy Policy explains what information AgentOS Studio collects, how it is used, and the choices you have. By using the Service, you agree to the practices described here.
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
          <Link to="/terms" className="text-primary-400 hover:text-primary-300 transition-colors">
            Read the Terms of Service →
          </Link>
        </div>
      </div>
    </div>
  )
}
