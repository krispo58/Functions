import os
import api_key
from llmapi import LLM

def test_context_and_logic():
    # 1. Initialize the LLM
    # Note: Ensure GEMINI_API_KEY and GROQ_API_KEY are in your environment
    ai = LLM()

    print("--- Starter test av kontekst (Turn 1) ---")
    # We give it a specific fact to remember
    response1 = ai.prompt("Hei! Mitt navn er Ola, og jeg skriver en oppgave om Hamsun.")
    print(f"Svar 1: {response1[:50]}...") # Print only the start to save console space

    print("\n--- Verifiserer minne (Turn 2) ---")
    # We ask it to recall that fact
    response2 = ai.prompt("Hva heter jeg, og hva skriver jeg om?")
    print(f"Svar 2: {response2}")

    # Validation logic
    if "Ola" in response2 and "Hamsun" in response2:
        print("\n✅ SUCCESS: Modellen husker kontekst.")
    else:
        print("\n❌ FAIL: Modellen mistet konteksten.")

def test_fallback_logic():
    print("\n--- Tester Fallback-logikk (Simulert) ---")
    # We force a failure by providing a fake model name for Gemini
    ai_fallback = LLM(gemini_model="non-existent-model-123")
    
    response = ai_fallback.prompt("Dette skal trigge fallback til Groq. Svar kort: Fungerer det?")
    
    if ai_fallback.use_fallback:
        print(f"Svar: {response}")
        print("✅ SUCCESS: Fallback til Groq ble aktivert automatisk.")
    else:
        print("❌ FAIL: Fallback ble ikke trigget.")

if __name__ == "__main__":
    # Test 1: Context (Normal usage)
    test_context_and_logic()
    
    # Test 2: Fallback (Verification)
    # Warning: Only run this if you want to verify the switch works. 
    # It will use one Groq call.
    test_fallback_logic()