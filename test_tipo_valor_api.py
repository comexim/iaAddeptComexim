import asyncio
from app.core.ada_api_client import ada_api_client

async def main():
    result = await ada_api_client.consultar_campo('tipoValor', '')
    
    if isinstance(result, dict) and 'registros' in result:
        registros = result['registros']
        print(f'Total de registros: {len(registros)}')
        print()
        for r in registros:
            codigo = r.get('codigo', 'N/A')
            descricao = r.get('descricao', 'N/A')
            print(f"Codigo: {codigo:<5} | Descricao: {descricao}")
    else:
        print("Resultado completo:")
        print(result)

if __name__ == '__main__':
    asyncio.run(main())
