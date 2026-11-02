// Precaricato da tests/conftest.py in ogni Node dei test: navigator.language arriva dalla lingua del sistema (inglese sui server
// di GitHub, italiano sul PC) e l'app sceglierebbe la lingua di conseguenza. Qui vale sempre l'italiano, uguale su ogni macchina.
// Configurabile: i test che provano un'altra lingua la ridefiniscono.
Object.defineProperty(globalThis, "navigator", { value: { language: "it-IT", languages: ["it-IT"] }, configurable: true, writable: true });
