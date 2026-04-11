
import asyncio
from dotenv import load_dotenv
load_dotenv()
from src.graph.builder import build_graph
from langchain_core.messages import HumanMessage

async def main():
    app = build_graph()
    state = {'messages': [HumanMessage(content='Analyze MSFT')], 'locale': 'en-US', 'research_topic': 'MSFT', 'final_report': '', 'raw_data_mode': False}
    print('Starting graph...')
    async for output in app.astream(state, {'recursion_limit': 50}):
        print('---------------------')
        print(output)
        print('---------------------')

if __name__ == '__main__':
    asyncio.run(main())
