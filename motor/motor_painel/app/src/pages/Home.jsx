export default function Home() {
  return (
    <div>
      <span className="num">Home</span>
      <div className="card" style={{ padding: 40, textAlign: 'center', marginTop: 16 }}>
        <div className="title" style={{ fontSize: 17, color: 'var(--text2)' }}>
          Painel da Meta-fábrica
        </div>
        <div className="mono" style={{ fontSize: 12, color: 'var(--text3)', marginTop: 8 }}>
          Navegue pela sidebar · Tela de prova: Runs
        </div>
      </div>
    </div>
  );
}
