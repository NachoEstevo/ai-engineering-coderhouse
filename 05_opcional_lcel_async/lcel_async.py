import asyncio
import os

from dotenv import load_dotenv
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI


def build_chain():
    model = ChatOpenAI(
        model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        temperature=0.2,
    )
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", "Respondé en español de manera breve y clara."),
            ("human", "{pregunta}"),
        ]
    )
    return prompt | model | StrOutputParser()


async def main() -> None:
    load_dotenv()
    if not os.getenv("OPENAI_API_KEY"):
        print("Definí OPENAI_API_KEY en el archivo .env antes de ejecutar el script.")
        return

    chain = build_chain()
    respuesta = await chain.ainvoke({"pregunta": "¿Qué es LCEL en LangChain?"})
    print(respuesta)


if __name__ == "__main__":
    asyncio.run(main())
