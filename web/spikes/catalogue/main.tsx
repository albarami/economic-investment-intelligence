import { createRoot } from 'react-dom/client';

const root = document.getElementById('root');
if (!root) throw new Error('Missing spike root');
createRoot(root).render(
  <main>
    <h1>Catalogue enforcement spike</h1>
    <p>
      Offline protocol evidence is recorded separately. Browser evidence awaits
      the lead.
    </p>
    <p>Fact display awaits the application component.</p>
  </main>,
);
