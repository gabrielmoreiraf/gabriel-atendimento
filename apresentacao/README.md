# Deck do pitch

`index.html` abre direto no navegador, sem servidor.

- **Navegar:** setas, espaço ou clique. `#5` na URL abre o slide 5.
- **Notas do apresentador:** tecla `N`. Cada número do deck tem a fonte na nota do slide.
- **PDF:** tecla `P` (ou Ctrl/Cmd+P), destino "Salvar como PDF", sem margens, com gráficos de fundo. Sai um slide por página em 1280×720. Para imprimir com as notas, aperte `N` antes.
- **Demo (slide 8):** a mídia vem da jornada E2E em `.scratch/e2e/`: `jornada.webm` → `midia/demo.webm`, `jornada.mp4` → `midia/demo.mp4` e um print → `midia/demo.png`. O navegador toca o primeiro formato que suportar (Chromium sem codecs proprietários não toca `.mp4`). No PDF entra o print.

Identidade visual: os valores de `tokens.css` e `DESIGN.md` (raiz) estão copiados no `<style>` do deck para ele abrir sozinho. A fonte IBM Plex vem do Google Fonts; sem internet, cai na fonte do sistema.

Números: `ingestao/baseline_metricas.md`, `ingestao/avaliacao_offline.md`, `docs/parametros.md` e `docs/politicas.csv`.

Os números dos slides 6 e 9 e da seção "Resultados medidos" do `README.md` da raiz vêm da avaliação offline e ficam entre marcadores `<!--av:chave-->…<!--/av-->`. Depois de regerar a avaliação, rode na raiz:

```bash
python3 -I apresentacao/atualizar_numeros.py
```

O script usa só as divergências por regra objetiva (soma da alçada, prazo, antes da entrega, 2ª troca). `acao_nao_permitida` fica de fora porque depende da tag humana e o relatório a trata como teto.
