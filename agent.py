import os                           # leitura de variáveis de ambiente
import re                           # extração do nome/argumento da ferramenta via regex
import requests                     # chamadas HTTP à API OMDb
import google.generativeai as genai # cliente oficial do Gemini
from dotenv import load_dotenv      # leitura do arquivo .env

# carrega as variáveis de ambiente do arquivo .env
load_dotenv()

# configura o cliente Gemini e as credenciais da API OMDb
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
OMDB_KEY = os.getenv("OMDB_API_KEY")
OMDB_URL = "http://www.omdbapi.com/"


# --- Ferramentas ---

def buscar_serie(nome: str) -> str:
    # busca metadados da série por nome e retorna título, imdbID, notas e sinopse
    resp = requests.get(OMDB_URL, params={"t": nome, "type": "series", "apikey": OMDB_KEY})
    data = resp.json()
    if data.get("Response") == "False":
        return f"Série não encontrada: {data.get('Error', 'erro desconhecido')}"
    # transforma a lista de ratings em dicionário {fonte: valor} para acesso direto
    notas = {r["Source"]: r["Value"] for r in data.get("Ratings", [])}
    return (
        f"Título: {data.get('Title')}\n"
        f"imdbID: {data.get('imdbID')}\n"
        f"Sinopse: {data.get('Plot')}\n"
        f"Ano: {data.get('Year')}\n"
        f"Status: {data.get('totalSeasons')} temporadas\n"
        f"Gêneros: {data.get('Genre')}\n"
        f"IMDb: {notas.get('Internet Movie Database', 'N/A')}\n"
        f"Rotten Tomatoes: {notas.get('Rotten Tomatoes', 'N/A')}\n"
        f"Metacritic: {notas.get('Metacritic', 'N/A')}"
    )


def buscar_elenco(imdb_id: str) -> str:
    # usa o imdbID (obtido via buscar_serie) para retornar o elenco principal
    resp = requests.get(OMDB_URL, params={"i": imdb_id.strip(), "apikey": OMDB_KEY})
    data = resp.json()
    if data.get("Response") == "False":
        return f"Elenco não encontrado: {data.get('Error', 'erro desconhecido')}"
    return f"Elenco principal de {data.get('Title')}: {data.get('Actors')}"


def buscar_episodios_da_temporada(imdb_id_e_temporada: str) -> str:
    # argumento esperado no formato "imdbID, numero_da_temporada"
    partes = imdb_id_e_temporada.split(",")
    imdb_id = partes[0].strip()
    temporada = partes[1].strip()
    resp = requests.get(OMDB_URL, params={"i": imdb_id, "Season": temporada, "apikey": OMDB_KEY})
    data = resp.json()
    if data.get("Response") == "False":
        return f"Episódios não encontrados: {data.get('Error', 'erro desconhecido')}"
    episodios = data.get("Episodes", [])
    # constrói a resposta linha a linha: cabeçalho + um episódio por linha
    linhas = [f"Temporada {temporada} de {data.get('Title', imdb_id)}:"]
    for ep in episodios:
        linhas.append(f"  E{ep['Episode']}: {ep['Title']} — IMDb: {ep['imdbRating']}")
    return "\n".join(linhas)


def calcular_tempo_de_maratona(episodios_e_minutos: str) -> str:
    # argumento esperado no formato "num_episodios, minutos_por_episodio"
    partes = episodios_e_minutos.split(",")
    episodios = int(partes[0].strip())
    minutos_por_ep = float(partes[1].strip())
    # converte progressivamente: minutos → horas → dias
    total_min = episodios * minutos_por_ep
    total_horas = total_min / 60
    total_dias = total_horas / 24
    return (
        f"Total: {total_min:.2f} minutos | "
        f"{total_horas:.2f} horas | "
        f"{total_dias:.2f} dias"
    )


# --- System prompt ---

# instrui o modelo a seguir o padrão ReAct: Thought → Action → PAUSE → Observation → Answer
system_prompt = """
You run in a loop of Thought, Action, PAUSE, Observation.
At the end of the loop you output an Answer.
Use Thought to describe your reasoning about the question you have been asked.
Use Action to call one of the available tools, then return PAUSE.
Observation will be the result of running that tool.
Always write PAUSE on a new line, never on the same line as the Action.

IMPORTANT:
Always start your response with Thought before any Action.
Never output an Action without a preceding Thought in the same response.

PRIORITIES:
1. Always call buscar_serie FIRST to obtain the imdbID before using any other tool.
2. Only call buscar_elenco if the user asks about cast or actors.
3. Only call buscar_episodios_da_temporada if the user asks specifically about a single season.
4. Only call calcular_tempo_de_maratona if the user asks about watch time or marathon duration.
5. As soon as you have enough information to answer the question, output the Answer and stop.

STRICT RULES:
- Never call buscar_episodios_da_temporada multiple times to cover all seasons of a series.
- To estimate full series marathon time, use the total seasons from buscar_serie, assume 20 episodes
  per season if unknown, and 45 minutes per episode if duration is not provided. Then call
  calcular_tempo_de_maratona once with the total estimated number of episodes and duration.
- Do not call tools that are unnecessary for the question asked.
- If the user's message is a greeting, farewell, or casual conversation, answer directly without calling any tool.
- If you cannot determine which series the user is referring to, output the clarification request directly as an Answer and stop. Never repeat a clarification request.
- If at any point you realize you do not have enough information to proceed, output it as an Answer and stop immediately.
- Never output the same response twice. If you find yourself about to repeat a previous response, stop and output an Answer instead.

Your available actions are:

buscar_serie:
e.g. buscar_serie: Breaking Bad
Searches for a TV series by name. Returns title, imdbID, plot, year, total seasons, genres,
and ratings from IMDb, Rotten Tomatoes and Metacritic.

buscar_elenco:
e.g. buscar_elenco: tt0903747
Returns the main cast of a TV series. Argument must be the imdbID from buscar_serie.

buscar_episodios_da_temporada:
e.g. buscar_episodios_da_temporada: tt0903747, 1
Returns the episode list and IMDb ratings for a specific season.
Argument must be a single string in the format "imdbID, season_number".

calcular_tempo_de_maratona:
e.g. calcular_tempo_de_maratona: 62, 47
Calculates total marathon time. No API call needed.
Argument must be a single string in the format "number_of_episodes, minutes_per_episode".

EXAMPLE SESSION:

Example session:

Question: Is Severance worth watching?

Thought: The user wants to know if Severance is worth watching. I should search for the series to get its ratings and plot, then give a recommendation.
Action: buscar_serie: Severance
PAUSE

You will be called again with this:

Observation: Título: Severance
imdbID: tt11972234
Sinopse: Mark leads a team of office workers whose memories have been surgically divided between their work and personal lives.
Ano: 2022-
Status: 2 temporadas
Gêneros: Drama, Mystery, Sci-Fi, Thriller
IMDb: 8.7/10
Rotten Tomatoes: 97%
Metacritic: 85/100

Thought: I now have the ratings and plot of Severance. With an 8.7 on IMDb and 97% on Rotten Tomatoes, I have enough information to give a solid recommendation without calling any other tool.

If you have the answer, output it as the Answer.

Answer: Severance is highly recommended. It holds an 8.7 on IMDb and 97% on Rotten Tomatoes, which puts it among the best recent series. It follows office workers whose work and personal memories are surgically separated, making for a unique and gripping premise. If you enjoy mystery and psychological drama, it is definitely worth watching.

Now it's your turn:
"""

# --- Classe Agent ---

class Agent:
    def __init__(self, model, system):
        self.model = model
        self.system = system   # system prompt já aplicado via system_instruction no modelo
        self.messages = []     # histórico de mensagens da conversa

    def __call__(self, message):
        # acumula o contexto e envia ao modelo para gerar a próxima resposta
        self.messages.append({"role": "user", "parts": [message]})
        result = self.execute()
        self.messages.append({"role": "model", "parts": [result]})
        return result

    def execute(self):
        # envia o histórico completo para manter o contexto multi-turno
        response = self.model.generate_content(self.messages)
        return response.text


# --- Loop principal do agente ---

def agent_loop(max_iterations, system, query):
    # system_instruction injeta o system prompt em todas as chamadas sem poluir o histórico
    model = genai.GenerativeModel(model_name="gemini-3.1-flash-lite-preview", system_instruction=system)
    agent = Agent(model, system)
    # nomes das funções disponíveis para despacho dinâmico
    tools = ["buscar_serie", "buscar_elenco", "buscar_episodios_da_temporada", "calcular_tempo_de_maratona"]

    next_prompt = query
    i = 0

    # max_iterations evita loop infinito caso o modelo nunca produza "Answer:"
    while i < max_iterations:
        i += 1
        result = agent(next_prompt)
        print(result)

        # encerra o loop quando o modelo produz a resposta final
        if "Answer:" in result:
            break

        # detecta o padrão ReAct e executa a ferramenta indicada pelo modelo
        if "PAUSE" in result and "Action" in result:
            # regex captura (nome_da_ferramenta, argumento) no formato "Action: tool: arg"
            match = re.findall(r"Action: ([a-z_]+): (.+)", result, re.IGNORECASE)
            if match:
                chosen_tool, arg = match[0]  # usa apenas a primeira ação encontrada
                arg = arg.strip()
                if chosen_tool in tools:
                    # despacha a chamada de ferramenta dinamicamente pelo nome
                    result_tool = eval(f"{chosen_tool}({repr(arg)})")
                else:
                    result_tool = "tool not found."
                # injeta o resultado como observação para a próxima iteração
                next_prompt = f"Observation: {result_tool}"


# --- Entrada do usuário ---

if __name__ == "__main__":
    print("Agente de séries de TV. Digite 'sair' para encerrar.\n")
    while True:
        pergunta = input("Você: ").strip()
        if pergunta.lower() == "sair":
            print("Até logo!")
            break
        if not pergunta:  # ignora envios vazios (Enter sem texto)
            continue
        print()
        agent_loop(max_iterations=6, system=system_prompt, query=pergunta)
        print()
