import React, { useEffect, useState } from 'react'
import ReactDOM from 'react-dom/client'
import './index.css'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { AuthProvider, useAuth } from './auth'
import { ThemeProvider } from './theme'
import { api } from './api'
import { AppShell } from './components/NavBar'
import { Login } from './pages/Login'
import { Projects } from './pages/Projects'
import { Board } from './pages/Board'
import { ExperimentsPage } from './pages/ExperimentsPage'
import { ProfilePage } from './pages/ProfilePage'
import { Setup } from './pages/Setup'
import { ProjectReportPage } from './pages/ProjectReportPage'
import { GlobalReportPage }   from './pages/GlobalReportPage'
import { UsersPage }          from './pages/UsersPage'

import { LabsPage }           from './pages/LabsPage'
import { LabDetail }          from './pages/LabDetail'
import { AdminDashboard }     from './pages/AdminDashboard'
import { AnalyticsPage }      from './pages/AnalyticsPage'
import { ImpactPage }         from './pages/ImpactPage'
import { ResearchMemoryPage } from './pages/ResearchMemoryPage'
import { StudentProfilePage } from './pages/StudentProfilePage'
import { GrantsPage }         from './pages/GrantsPage'
import { GrantDetail }        from './pages/GrantDetail'
import { ConferencesPage }    from './pages/ConferencesPage'
import { IRBPage }            from './pages/IRBPage'
import { WikiPages }          from './pages/WikiPages'
import { WikiPageView }       from './pages/WikiPageView'
import { PublicationsPage }   from './pages/PublicationsPage'
import { PublicationDetail }  from './pages/PublicationDetail'
import { SystemHealthPage }   from './pages/SystemHealthPage'
import { SettingsPage }       from './pages/SettingsPage'
import { HelpPage }           from './pages/HelpPage'
import { AppsPage }           from './pages/AppsPage'
import { ProjectDataPage }    from './pages/ProjectDataPage'
import { HomePage }           from './pages/HomePage'
import { WeeklyUpdatePage }   from './pages/WeeklyUpdatePage'
import { WeeklyMeetingPage }  from './pages/WeeklyMeetingPage'
import { SupervisionReportsPage } from './pages/SupervisionReportsPage'
import { JourneyPage }        from './pages/JourneyPage'
import { RequirementsPage }   from './pages/RequirementsPage'
import { ProfessorDashboardPage } from './pages/ProfessorDashboardPage'
import { ResearchItemsPage }  from './pages/ResearchItemsPage'
import { PaperStudioPage }   from './pages/PaperStudioPage'

const queryClient = new QueryClient()

function PrivateRoute({ children }: { children: React.ReactNode }) {
  const { token } = useAuth()
  return token ? <AppShell>{children}</AppShell> : <Navigate to="/login" replace />
}

function App() {
  const [needsSetup, setNeedsSetup] = useState<boolean | null>(null)

  useEffect(() => {
    api.setupStatus().then(r => setNeedsSetup(r.needs_setup)).catch(() => setNeedsSetup(false))
  }, [])

  // JSX text is literal, so "\u2026" here would render as those six characters.
  if (needsSetup === null) return <p style={{ padding: 24 }}>Loading…</p>

  return (
    <BrowserRouter>
      <Routes>
        {needsSetup && <Route path="*" element={<Setup />} />}
        <Route path="/login" element={<Login />} />
        <Route path="/home" element={<PrivateRoute><HomePage /></PrivateRoute>} />
        <Route path="/professor" element={<PrivateRoute><ProfessorDashboardPage /></PrivateRoute>} />
        <Route path="/weekly-update" element={<PrivateRoute><WeeklyUpdatePage /></PrivateRoute>} />
        <Route path="/meeting" element={<PrivateRoute><WeeklyMeetingPage /></PrivateRoute>} />
        <Route path="/supervision/reports" element={<PrivateRoute><SupervisionReportsPage /></PrivateRoute>} />
        <Route path="/journey" element={<PrivateRoute><JourneyPage /></PrivateRoute>} />
        <Route path="/requirements" element={<PrivateRoute><RequirementsPage /></PrivateRoute>} />
        <Route path="/research-items" element={<PrivateRoute><ResearchItemsPage /></PrivateRoute>} />
        <Route path="/publications/:id/workspace" element={<PrivateRoute><PaperStudioPage /></PrivateRoute>} />
        <Route path="/publications/:id/studio" element={<PrivateRoute><PaperStudioPage /></PrivateRoute>} />
        <Route path="/admissions" element={<Navigate to="/home" replace />} />
        <Route path="/admissions/:id" element={<Navigate to="/home" replace />} />
        <Route path="/projects" element={<PrivateRoute><Projects /></PrivateRoute>} />
        <Route path="/projects/:id" element={<PrivateRoute><Board /></PrivateRoute>} />
        <Route path="/projects/:id/experiments" element={<PrivateRoute><ExperimentsPage /></PrivateRoute>} />
        <Route path="/projects/:id/data" element={<PrivateRoute><ProjectDataPage /></PrivateRoute>} />
        <Route path="/projects/:id/report" element={<PrivateRoute><ProjectReportPage /></PrivateRoute>} />
        <Route path="/reports"             element={<PrivateRoute><GlobalReportPage /></PrivateRoute>} />
        <Route path="/profile" element={<PrivateRoute><ProfilePage /></PrivateRoute>} />
        <Route path="/users"   element={<PrivateRoute><UsersPage /></PrivateRoute>} />
        <Route path="/labs"            element={<PrivateRoute><LabsPage /></PrivateRoute>} />
        <Route path="/labs/:id"        element={<PrivateRoute><LabDetail /></PrivateRoute>} />
        <Route path="/labs/:id/impact" element={<PrivateRoute><ImpactPage /></PrivateRoute>} />
        <Route path="/labs/:id/research-memory" element={<PrivateRoute><ResearchMemoryPage /></PrivateRoute>} />
        <Route path="/students/:id" element={<PrivateRoute><StudentProfilePage /></PrivateRoute>} />
        <Route path="/research/evaluation" element={<Navigate to="/home" replace />} />
        <Route path="/admin"           element={<PrivateRoute><AdminDashboard /></PrivateRoute>} />
        <Route path="/analytics"       element={<PrivateRoute><AnalyticsPage /></PrivateRoute>} />
        <Route path="/grants"          element={<PrivateRoute><GrantsPage /></PrivateRoute>} />
        <Route path="/grants/:id"      element={<PrivateRoute><GrantDetail /></PrivateRoute>} />
        <Route path="/conferences"     element={<PrivateRoute><ConferencesPage /></PrivateRoute>} />
        <Route path="/irb"             element={<PrivateRoute><IRBPage /></PrivateRoute>} />
        <Route path="/labs/:id/wiki"   element={<PrivateRoute><WikiPages /></PrivateRoute>} />
        <Route path="/labs/:id/wiki/:slug" element={<PrivateRoute><WikiPageView /></PrivateRoute>} />
        <Route path="/publications"    element={<PrivateRoute><PublicationsPage /></PrivateRoute>} />
        <Route path="/publications/:id" element={<PrivateRoute><PublicationDetail /></PrivateRoute>} />
        <Route path="/apps"      element={<PrivateRoute><AppsPage /></PrivateRoute>} />
        <Route path="/health"    element={<PrivateRoute><SystemHealthPage /></PrivateRoute>} />
        <Route path="/settings"  element={<PrivateRoute><SettingsPage /></PrivateRoute>} />
        <Route path="/help"      element={<PrivateRoute><HelpPage /></PrivateRoute>} />
        {!needsSetup && <Route path="*" element={<Navigate to="/home" replace />} />}
      </Routes>
    </BrowserRouter>
  )
}

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <ThemeProvider>
        <AuthProvider>
          <App />
        </AuthProvider>
      </ThemeProvider>
    </QueryClientProvider>
  </React.StrictMode>,
)
