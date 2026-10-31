import { BrowserRouter, Route, Routes } from 'react-router'

import { AuthProvider } from './auth/AuthContext'
import { Layout } from './components/Layout'
import { ToastProvider } from './components/Toasts'
import { CatalogueProvider } from './lib/catalogue'
import { AdminFishForm } from './pages/admin/AdminFishForm'
import { AdminFishList } from './pages/admin/AdminFishList'
import { AdminLayout } from './pages/admin/AdminLayout'
import { AdminUsers } from './pages/admin/AdminUsers'
import { Account } from './pages/Account'
import { Catalogue } from './pages/Catalogue'
import { FishPage } from './pages/FishPage'
import { Home } from './pages/Home'
import { NewTank, NotFound } from './pages/Misc'
import { MyTanks } from './pages/MyTanks'
import { TankWorkspace } from './pages/TankWorkspace'

export function App() {
  return (
    <BrowserRouter>
      <ToastProvider>
        <AuthProvider>
          <CatalogueProvider>
            <Routes>
              <Route element={<Layout />}>
                <Route index element={<Home />} />
                <Route path="fish" element={<Catalogue />} />
                <Route path="fish/:id" element={<FishPage />} />
                <Route path="tanks/new" element={<NewTank />} />
                <Route path="tanks/:key" element={<TankWorkspace />} />
                <Route path="my-tanks" element={<MyTanks />} />
                <Route path="account" element={<Account />} />
                <Route path="*" element={<NotFound />} />
              </Route>
              <Route path="admin" element={<AdminLayout />}>
                <Route index element={<AdminFishList />} />
                <Route path="fish" element={<AdminFishList />} />
                <Route path="review" element={<AdminFishList review />} />
                <Route path="fish/new" element={<AdminFishForm />} />
                <Route path="fish/:id" element={<AdminFishForm />} />
                <Route path="users" element={<AdminUsers />} />
              </Route>
            </Routes>
          </CatalogueProvider>
        </AuthProvider>
      </ToastProvider>
    </BrowserRouter>
  )
}
