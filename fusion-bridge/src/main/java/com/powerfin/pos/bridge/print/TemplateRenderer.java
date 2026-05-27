package com.powerfin.pos.bridge.print;

import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.OutputStream;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;

import jakarta.annotation.PostConstruct;
import jakarta.enterprise.context.ApplicationScoped;

import org.eclipse.microprofile.config.inject.ConfigProperty;

import io.quarkus.logging.Log;

/**
 * Renders a receipt template with {{placeholders}} and formatting directives
 * into raw ESC/POS bytes for thermal printers.
 *
 * Directives:
 *   [BOLD]...[/BOLD]     — bold text
 *   [CENTER]...[/CENTER] — centred text
 *   ---                  — separator line (thin)
 *   ===                  — separator line (bold)
 *   {#customer}...{/customer} — conditional: visible only when customerName != null
 *   {#invoice}...{/invoice}   — conditional: visible only when invoiceId != null
 *   [CUT]                — full paper cut
 *   {{variable}}         — placeholder (see resolve())
 */
@ApplicationScoped
public class TemplateRenderer {

    // ── ESC/POS commands ──────────────────────────────────
    private static final byte ESC = 0x1B;
    private static final byte GS  = 0x1D;
    private static final byte[] BOLD_ON   = { ESC, '!', 0x08 };
    private static final byte[] BOLD_OFF  = { ESC, '!', 0x00 };
    private static final byte[] ALIGN_LEFT   = { ESC, 'a', 0x00 };
    private static final byte[] ALIGN_CENTER = { ESC, 'a', 0x01 };
    private static final byte[] CUT_FULL     = { GS,  'V', 0x00 };
    private static final byte[] LF = { '\n' };
    private static final int COLUMNS = 42;

    // ── Template storage ─────────────────────────────────
    private volatile String template;
    private final Path templateFile;
    private final String defaultTemplate;

    public TemplateRenderer(
            @ConfigProperty(name = "printer.template.file",
                defaultValue = "/var/lib/powerfin/pos/receipt-template.txt")
            String templateFilePath) {
        this.templateFile = Paths.get(templateFilePath);
        this.defaultTemplate = defaultTemplate();
    }

    @PostConstruct
    void init() {
        load();
    }

    /** Load template from file, falling back to default. */
    private void load() {
        if (templateFile != null && Files.exists(templateFile)) {
            try {
                template = Files.readString(templateFile, StandardCharsets.UTF_8);
                Log.infof("Template loaded from %s", templateFile);
                return;
            } catch (IOException e) {
                Log.warnf("Failed to load template from %s: %s", templateFile, e.getMessage());
            }
        }
        template = defaultTemplate;
        Log.info("Using default receipt template");
    }

    public String getTemplate() {
        return template;
    }

    /** Save a new template to disk + update in memory. */
    public void saveTemplate(String newTemplate) throws IOException {
        this.template = newTemplate;
        if (templateFile != null) {
            Files.createDirectories(templateFile.getParent());
            Files.writeString(templateFile, newTemplate, StandardCharsets.UTF_8);
            Log.infof("Template saved to %s", templateFile);
        }
    }

    // ── Render ───────────────────────────────────────────

    /**
     * Renders the current template with the given data into ESC/POS bytes.
     */
    public byte[] render(ReceiptBuilder.FuelReceiptData data) {
        ByteArrayOutputStream out = new ByteArrayOutputStream();
        String[] lines = template.split("\n");

        int i = 0;
        while (i < lines.length) {
            String line = lines[i];

            // Conditional blocks: {#customer}...{/customer}
            if (line.contains("{#customer}")) {
                i = skipConditional(lines, i, "{#customer}", "{/customer}",
                        data.customerName != null && !data.customerName.isEmpty(), out, data);
                continue;
            }
            if (line.contains("{#invoice}")) {
                i = skipConditional(lines, i, "{#invoice}", "{/invoice}",
                        data.invoiceId != null && !data.invoiceId.isEmpty(), out, data);
                continue;
            }

            renderLine(out, line, data);
            i++;
        }

        // Final cut if [CUT] wasn't in template
        try { out.write(CUT_FULL); } catch (IOException ignored) { }

        return out.toByteArray();
    }

    // ── Internal ─────────────────────────────────────────

    private int skipConditional(String[] lines, int start,
                                 String open, String close,
                                 boolean visible,
                                 OutputStream out,
                                 ReceiptBuilder.FuelReceiptData data) {
        int depth = 0;
        int i = start;
        while (i < lines.length) {
            String line = lines[i];

            // Track depth BEFORE processing close on same line
            int opens = countInLine(line, open);
            int closes = countInLine(line, close);
            depth += opens;

            if (depth > 0 && visible) {
                // Render this line stripped of tags
                String stripped = line.replace(open, "").replace(close, "");
                if (!stripped.isBlank()) {
                    renderLine(out, stripped, data);
                }
            }

            depth -= closes;
            i++;

            if (depth <= 0 && opens > 0) {
                // We opened and closed on this line (or opened earlier, closed now)
                break;
            }
            if (depth <= 0 && opens == 0 && i > start + 1) {
                // No open on this line, depth went to 0 from a close, done
                break;
            }
        }
        return i;
    }

    private int countInLine(String line, String tag) {
        int count = 0;
        int idx = 0;
        while ((idx = line.indexOf(tag, idx)) >= 0) {
            count++;
            idx += tag.length();
        }
        return count;
    }

    private void renderLine(OutputStream out, String line,
                             ReceiptBuilder.FuelReceiptData data) {
        try {
            // [CUT] directive
            if (line.trim().equals("[CUT]")) {
                out.write(LF);
                out.write(CUT_FULL);
                return;
            }

            // Formatting wrappers
            boolean bold = false;
            boolean center = false;

            while (line.contains("[BOLD]") && line.contains("[/BOLD]")) {
                bold = true;
                line = line.replace("[BOLD]", "").replace("[/BOLD]", "");
            }
            while (line.contains("[CENTER]") && line.contains("[/CENTER]")) {
                center = true;
                line = line.replace("[CENTER]", "").replace("[/CENTER]", "");
            }

            // Resolve placeholders
            line = resolve(line, data);

            // Separator lines
            boolean isThinSep  = line.trim().matches("-{3,}");
            boolean isBoldSep  = line.trim().matches("={3,}");

            if (isThinSep || isBoldSep) {
                out.write(LF);
                if (isBoldSep) out.write(BOLD_ON);
                byte[] dashes = repeat('-', COLUMNS);
                out.write(dashes);
                if (isBoldSep) out.write(BOLD_OFF);
                out.write(LF);
                return;
            }

            // Alignment
            if (center) out.write(ALIGN_CENTER);

            // Bold
            if (bold) out.write(BOLD_ON);

            // Text
            out.write(line.getBytes(StandardCharsets.UTF_8));
            out.write(LF);

            // Reset
            if (bold) out.write(BOLD_OFF);
            if (center) out.write(ALIGN_LEFT);

        } catch (IOException e) {
            Log.errorf("Template render error: %s", e.getMessage());
        }
    }

    /** Replace {{placeholders}} with actual values. */
    String resolve(String line, ReceiptBuilder.FuelReceiptData data) {
        return line
            .replace("{{location_name}}", nvl(data.locationName, "GASOLINERA"))
            .replace("{{location_address}}", nvl(data.locationAddress, ""))
            .replace("{{location_ruc}}", nvl(data.locationRuc, ""))
            .replace("{{date}}", nvl(data.date, ""))
            .replace("{{time}}", nvl(data.time, ""))
            .replace("{{dispenser_id}}", String.valueOf(data.dispenserId))
            .replace("{{hose_id}}", String.valueOf(data.hoseId))
            .replace("{{grade}}", nvl(data.grade, ""))
            .replace("{{volume}}", nvl(data.volume, "0.00"))
            .replace("{{unit_price}}", nvl(data.unitPrice, "0.00"))
            .replace("{{amount}}", nvl(data.amount, "0.00"))
            .replace("{{payment_method}}", nvl(data.paymentMethod, ""))
            .replace("{{customer_name}}", nvl(data.customerName, ""))
            .replace("{{plate}}", nvl(data.plate, ""))
            .replace("{{invoice_id}}", nvl(data.invoiceId, ""))
            .replace("{{invoice_auth}}", nvl(data.invoiceAuth, ""))
            .replace("{{order_id}}", nvl(data.orderId, ""));
    }

    private static String nvl(String s, String def) {
        return s != null && !s.isEmpty() ? s : def;
    }

    private static byte[] repeat(char c, int count) {
        byte[] b = new byte[count];
        for (int i = 0; i < count; i++) b[i] = (byte) c;
        return b;
    }

    // ── Default template ─────────────────────────────────

    public static String defaultTemplate() {
        return """
[CENTER][BOLD]{{location_name}}[/BOLD]
{{location_address}}
RUC: {{location_ruc}}[/CENTER]
---
Fecha: {{date}}  {{time}}
Surtidor: {{dispenser_id}}  Pistola: {{hose_id}}
[BOLD]{{grade}}[/BOLD]
---
Volumen (litros):         {{volume}}
Precio unitario:          ${{unit_price}}
===
[CENTER][BOLD]TOTAL:  ${{amount}}[/BOLD][/CENTER]
===
Pago: {{payment_method}}
{#customer}Cliente: {{customer_name}}
Placa: {{plate}}{/customer}
---
{#invoice}Factura: {{invoice_id}}
[CENTER]Autorizacion SRI
{{invoice_auth}}[/CENTER]
{/invoice}
---
[CENTER]Gracias por su preferencia[/CENTER]

[CUT]""";
    }
}
