# Agente de Séries de TV

Agente de IA conversacional que responde perguntas sobre séries de TV usando o ciclo ReAct (Thought → Action → PAUSE → Observation → Answer), sem uso de nenhum framework de agentes.

---

## O que o agente faz

O agente recebe perguntas em linguagem natural sobre séries de TV e responde usando ferramentas reais conectadas à OMDb API. Ele raciocina em voz alta (Thought), decide qual ferramenta chamar (Action), pausa para receber o resultado (Observation) e então formula uma resposta final (Answer).

Exemplos de perguntas que o agente sabe responder:

- "Qual é a sinopse de Stranger Things?"
- "Quem são os atores principais de The Bear?"
- "Me mostra os episódios da 1ª temporada de Breaking Bad com as notas do IMDb."
- "Quantas horas leva para maratonar 10 episódios de 45 minutos cada?"

---

## Ferramentas disponíveis e por que foram escolhidas

| Ferramenta | O que faz | Por que foi escolhida |
|---|---|---|
| `buscar_serie` | Busca informações gerais de uma série pelo nome (sinopse, ano, gêneros, notas) | Ponto de entrada obrigatório: fornece o `imdbID` que as demais ferramentas precisam |
| `buscar_elenco` | Retorna o elenco principal de uma série a partir do `imdbID` | Separada de `buscar_serie` para evitar respostas longas quando só o elenco importa |
| `buscar_episodios_da_temporada` | Lista episódios e notas do IMDb de uma temporada específica | Permite explorar o conteúdo temporada a temporada, útil para comparações |
| `calcular_tempo_de_maratona` | Calcula o tempo total de maratona em minutos, horas e dias | Ferramenta local (sem API) que mostra que nem toda ação precisa de chamada externa |

Todas as ferramentas recebem exatamente **um argumento do tipo string**, conforme exigido pelo mecanismo de despacho via `eval`. As que precisam de dois parâmetros recebem tudo em uma string e fazem o split internamente.

---

## Como rodar localmente

### 1. Acesse a pasta do projeto

```bash
cd agent_series
```

### 2. Crie e ative um ambiente virtual

```bash
python -m venv venv

# Windows (PowerShell)
venv\Scripts\Activate.ps1

# Linux/macOS
source venv/bin/activate
```

### 3. Instale as dependências

```bash
pip install -r requirements.txt
```

### 4. Configure as chaves de API no arquivo `.env`

Abra o arquivo `.env` e substitua os valores:

```env
GEMINI_API_KEY=sua_chave_aqui
OMDB_API_KEY=sua_chave_aqui
```

**Onde obter as chaves gratuitamente:**

- **Gemini API Key:** acesse o [Google AI Studio](https://aistudio.google.com/apikey), faça login com uma conta Google e clique em "Create API Key". O plano gratuito oferece um limite generoso de requisições por minuto.

- **OMDb API Key:** acesse [omdbapi.com/apikey.aspx](https://www.omdbapi.com/apikey.aspx), escolha o plano gratuito (1.000 requisições/dia) e informe seu e-mail. A chave chegará na caixa de entrada em instantes.

### 5. Execute o agente

```bash
python agent.py
```

Digite sua pergunta sobre séries e pressione Enter. Para encerrar, digite `sair`.

---

## O que aprendi e o que foi difícil

**O ciclo ReAct na prática:** implementar o padrão Thought/Action/PAUSE/Observation sem framework nenhum deixou claro o que os frameworks fazem por debaixo dos panos — basicamente um loop com parsing de texto e despacho de função. É simples, mas exige que o prompt seja muito preciso para o modelo seguir o formato corretamente.

**Formato de mensagens do Gemini:** a principal diferença em relação à OpenAI API é que o Gemini usa `"model"` no lugar de `"assistant"` e `"parts"` (lista) no lugar de `"content"` (string). Errar esse formato gera erros ou respostas inesperadas. O `system_instruction` também vai no construtor do modelo, não como mensagem no histórico.

**Ferramentas com um único argumento string:** o mecanismo de despacho via `eval` obriga todas as ferramentas a receberem exatamente uma string. Ferramentas que precisam de dois parâmetros (como `buscar_episodios_da_temporada`) fazem o parse internamente com `split(",")`. Isso funcionou bem, mas exige que o prompt instrua o modelo a formatar o argumento corretamente.

**Consistência do modelo ao seguir o formato:** o maior desafio foi fazer o LLM respeitar sempre o padrão `Action: ferramenta: argumento\nPAUSE`. A chave foi incluir um exemplo concreto no system prompt e ser explícito sobre o `PAUSE` obrigatório após cada ação — sem ele, o agente tenta responder sem esperar a Observation.
