# MCP-based SharePoint chatbot

**Project**: The SharePoint chatbot uses a RAG architecture in which SharePoint Search retrieves relevant information from internal documents, and MCP is used to separate the AI agent app from the implementation that exposes SharePoint functionality.

**Consumer**: Contra Costa County Employment and Human Services Department, CA

**Program languages**: Python, JavaScript

**Python libraries are used**: requests, json, HttpNegotiateAuth, CORSMiddleware, MCPServer, BytesIO, Document, PdfReader, load_workbook

**Description**: 
The chatbot lets users ask ordinary questions about information stored on the SharePoint site. It combines SharePoint Search Engine with MCP to connect any AI-agent and produce concise answers grounded in information retrieved from SharePoint.
MCP stands for Model Context Protocol. It defines a common protocol for communication between an AI application and external capabilities, such as data sources, APIs, and tools.

The chatbot workflow:
1. The user enters a question in everyday language; no SharePoint search syntax is required.
2. JavaScript on SharePoint site sent the request to the backend server.
3. Backend server processes the request and sent it to ChatGPT through OpenAI API.
4. The request is converted into a concise search phrase intended to locate the most relevant SharePoint information.
5. SharePoint Search finds matching documents and returns their titles, links, file types, relevance ranks, and short search snippets.
6. The relevant SharePoint results and snippets become the source material used to answer the user's questions.
7. GPT is instructed to answer only from the supplied SharePoint information. If the results are insufficient, it should say that the information was not found.
8. The chatbot displays the documents found by SharePoint, with links, ranks, and snippets, allowing users to open and review the source material themselves.

The project file structure:
 - agent_backend
    - main.py - agent backend script
 - mcp_server
   - server.py - MCP server script 
 - ChatBotMCP.html - frontend JS-script and HTML chatbot web interface

**Results / Key Findings:** The chatbot connects artificial intelligence to the organization’s knowledge base to provide accurate answers based on up-to-date company documents, rather than just the neural network’s collective memory. 

**Illustrations**: Workflow diagram

![alt text](https://github.com/dmitrii-govorukhin/MCP-based_SharePoint_chatbot/blob/main/SharePoint_Chatbot_with_MCP.png?raw=true)
