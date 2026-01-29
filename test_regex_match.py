import re

query = "Dos contratos que já embarcaram em janeiro 2026, quantos já foram baixados no contas a receber?"

old_pattern = r'embarcad[oa]s?.*baixad[oa]s?|baixad[oa]s?.*embarcad[oa]s?'
new_pattern = r'embarc(ad[oa]s?|aram|ou|am).*baix(ad[oa]s?|aram|ou|am)|baix(ad[oa]s?|aram|ou|am).*embarc(ad[oa]s?|aram|ou|am)'

old_match = re.search(old_pattern, query.lower())
new_match = re.search(new_pattern, query.lower())

print(f"Query: {query}")
print(f"Query lowercase: {query.lower()}")
print(f"\nOld Pattern: {old_pattern}")
print(f"Old Match: {old_match}")

print(f"\nNew Pattern: {new_pattern}")
print(f"New Match: {new_match}")
if new_match:
    print(f"Matched text: {new_match.group()}")
