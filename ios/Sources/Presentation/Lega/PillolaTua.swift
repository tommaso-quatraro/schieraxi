import SwiftUI

/// La pillola «tua» accanto al nome della propria squadra nell'elenco delle squadre.
struct PillolaTua: View {
    var body: some View {
        Text("tua")
            .font(.caption2.bold())
            .padding(.horizontal, 6).padding(.vertical, 2)
            .background(Color.verde.opacity(0.3), in: Capsule())
    }
}
