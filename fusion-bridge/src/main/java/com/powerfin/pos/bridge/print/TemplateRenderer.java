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
    private static final byte[] BOLD_ON   = { ESC, 'E', 1 };         // Bold ON (independent of font)
    private static final byte[] BOLD_OFF  = { ESC, 'E', 0 };         // Bold OFF
    private static final byte[] ALIGN_LEFT   = { ESC, 'a', 0x00 };
    private static final byte[] ALIGN_CENTER = { ESC, 'a', 0x01 };
    private static final byte[] FONT_SMALL  = { ESC, 'M', 1 };       // Font B (9x17, compact)
    private static final byte[] LINE_SPACING_0 = { ESC, '3', 0 };    // Minimal line spacing
    private static final byte[] CUT_FULL    = { GS, 'V', 0x00 };
    private static final byte[] LF = { '\n' };
    private static final int COLUMNS = 50;  // Font B (9×17) ≈ 50 chars/line

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

        // Set Font B (small/compact) + minimal line spacing
        try { out.write(FONT_SMALL); out.write(LINE_SPACING_0); } catch (IOException ignored) { }

        int i = 0;
        while (i < lines.length) {
            String line = lines[i];

            // Skip blank lines
            if (line.isBlank()) {
                i++;
                continue;
            }

            // Conditional blocks
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
            if (line.contains("{#plate}")) {
                i = skipConditional(lines, i, "{#plate}", "{/plate}",
                        data.plate != null && !data.plate.isEmpty(), out, data);
                continue;
            }
            if (line.contains("{#customer_address}")) {
                i = skipConditional(lines, i, "{#customer_address}", "{/customer_address}",
                        data.customerAddress != null && !data.customerAddress.isEmpty(), out, data);
                continue;
            }
            if (line.contains("{#customer_email}")) {
                i = skipConditional(lines, i, "{#customer_email}", "{/customer_email}",
                        data.customerEmail != null && !data.customerEmail.isEmpty(), out, data);
                continue;
            }
            if (line.contains("{#subsidy_amount}")) {
                i = skipConditional(lines, i, "{#subsidy_amount}", "{/subsidy_amount}",
                        data.subsidyAmount != null && !data.subsidyAmount.isEmpty(), out, data);
                continue;
            }
            if (line.contains("{#subtotal}")) {
                i = skipConditional(lines, i, "{#subtotal}", "{/subtotal}",
                        data.subtotal != null && !data.subtotal.isEmpty(), out, data);
                continue;
            }
            if (line.contains("{#price_without_subsidy}")) {
                i = skipConditional(lines, i, "{#price_without_subsidy}", "{/price_without_subsidy}",
                        data.priceWithoutSubsidy != null && !data.priceWithoutSubsidy.isEmpty(), out, data);
                continue;
            }

            renderLine(out, line, data);
            i++;
        }

        // Feed blank lines + dot so paper advances well past the cutter
        try {
            for (int j = 0; j < 6; j++) out.write(LF);
            out.write(".".getBytes(StandardCharsets.UTF_8));
            out.write(LF);
            out.write(CUT_FULL);
        } catch (IOException ignored) { }

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
                // Strip ALL conditional tags (including nested ones)
                String stripped = line
                        .replace(open, "")
                        .replace(close, "")
                        .replaceAll("\\{#[a-z_]+\\}", "")
                        .replaceAll("\\{/[a-z_]+\\}", "");
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
            .replace("{{location_phone}}", nvl(data.locationPhone, ""))
            .replace("{{location_city}}", nvl(data.locationCity, ""))
            .replace("{{location_province}}", nvl(data.locationProvince, ""))
            .replace("{{location_country}}", nvl(data.locationCountry, ""))
            .replace("{{fiscal_regime}}", nvl(data.fiscalRegime, ""))
            .replace("{{sri_environment}}", data.sriEnvironment > 0 ? (data.sriEnvironment == 2 ? "PRODUCCION" : "PRUEBAS") : "")
            .replace("{{emission_type}}", data.emissionType == 1 ? "NORMAL" : "")
            .replace("{{date}}", nvl(data.date, ""))
            .replace("{{time}}", nvl(data.time, ""))
            .replace("{{dispenser_id}}", String.valueOf(data.dispenserId))
            .replace("{{hose_id}}", String.valueOf(data.hoseId))
            .replace("{{grade}}", nvl(data.grade, ""))
            .replace("{{volume}}", nvl(data.volume, "0.00"))
            .replace("{{unit_price}}", nvl(data.unitPrice, "0.00"))
            .replace("{{price_without_subsidy}}", nvl(data.priceWithoutSubsidy, ""))
            .replace("{{subsidy_per_unit}}", nvl(data.subsidyPerUnit, ""))
            .replace("{{subsidy_amount}}", nvl(data.subsidyAmount, ""))
            .replace("{{amount}}", nvl(data.amount, "0.00"))
            .replace("{{payment_method}}", nvl(data.paymentMethod, ""))
            .replace("{{customer_name}}", nvl(data.customerName, ""))
            .replace("{{customer_id}}", nvl(data.customerId, ""))
            .replace("{{customer_address}}", nvl(data.customerAddress, ""))
            .replace("{{customer_phone}}", nvl(data.customerPhone, ""))
            .replace("{{customer_email}}", nvl(data.customerEmail, ""))
            .replace("{{plate}}", nvl(data.plate, ""))
            .replace("{{invoice_id}}", nvl(data.invoiceId, ""))
            .replace("{{invoice_auth}}", nvl(data.invoiceAuth, ""))
            .replace("{{order_id}}", nvl(data.orderId, ""))
            .replace("{{subtotal}}", nvl(data.subtotal, ""))
            .replace("{{tax_label}}", nvl(data.taxLabel, "IVA"))
            .replace("{{tax_amount}}", nvl(data.taxAmount, ""))
            .replace("{{unit}}", nvl(data.unit, "GAL"));
    }

    private static String nvl(String s, String def) {
        return s != null && !s.isEmpty() ? s : def;
    }

    private static byte[] repeat(char c, int count) {
        byte[] b = new byte[count];
        for (int i = 0; i < count; i++) b[i] = (byte) c;
        return b;
    }

    // ── Cash movement receipt ───────────────────────────

    /** Renders a cash movement receipt with its own template. */
    public byte[] renderCashMovement(ReceiptBuilder.CashMovementData data) {
        ByteArrayOutputStream out = new ByteArrayOutputStream();
        String[] lines = cashMovementTemplate().split("\n");

        // Set Font B (small/compact) + minimal line spacing
        try { out.write(FONT_SMALL); out.write(LINE_SPACING_0); } catch (IOException ignored) { }

        for (String line : lines) {
            if (line.isBlank()) continue;

            try {
                if (line.trim().equals("[CUT]")) {
                    for (int j = 0; j < 6; j++) out.write(LF);
                    out.write(".".getBytes(StandardCharsets.UTF_8));
                    out.write(LF);
                    out.write(CUT_FULL);
                    continue;
                }

                boolean bold = false;
                boolean center = false;
                String resolved = line;

                while (resolved.contains("[BOLD]") && resolved.contains("[/BOLD]")) {
                    bold = true;
                    resolved = resolved.replace("[BOLD]", "").replace("[/BOLD]", "");
                }
                while (resolved.contains("[CENTER]") && resolved.contains("[/CENTER]")) {
                    center = true;
                    resolved = resolved.replace("[CENTER]", "").replace("[/CENTER]", "");
                }

                // Resolve cash placeholders
                resolved = resolved
                    .replace("{{location_name}}", nvl(data.locationName, "GASOLINERA"))
                    .replace("{{location_address}}", nvl(data.locationAddress, ""))
                    .replace("{{location_ruc}}", nvl(data.locationRuc, ""))
                    .replace("{{location_phone}}", nvl(data.locationPhone, ""))
                    .replace("{{movement_type}}", movementLabel(data.movementType))
                    .replace("{{date}}", nvl(data.date, ""))
                    .replace("{{time}}", nvl(data.time, ""))
                    .replace("{{user_name}}", nvl(data.userName, ""))
                    .replace("{{amount}}", nvl(data.amount, "0.00"))
                    .replace("{{observation}}", nvl(data.observation, ""));

                boolean isSep = resolved.trim().matches("-{3,}") || resolved.trim().matches("={3,}");
                if (isSep) {
                    out.write(LF);
                    byte[] dashes = repeat('-', COLUMNS);
                    out.write(dashes);
                    out.write(LF);
                    continue;
                }

                if (center) out.write(ALIGN_CENTER);
                if (bold) out.write(BOLD_ON);

                out.write(resolved.getBytes(StandardCharsets.UTF_8));
                out.write(LF);

                if (bold) out.write(BOLD_OFF);
                if (center) out.write(ALIGN_LEFT);

            } catch (IOException e) {
                Log.errorf("Cash receipt render error: %s", e.getMessage());
            }
        }

        // Final feed + dot + cut
        try {
            for (int j = 0; j < 6; j++) out.write(LF);
            out.write(".".getBytes(StandardCharsets.UTF_8));
            out.write(LF);
            out.write(CUT_FULL);
        } catch (IOException ignored) { }

        return out.toByteArray();
    }

    private static String movementLabel(String type) {
        if (type == null) return "";
        return switch (type.toUpperCase()) {
            case "INCOME" -> "COMPROBANTE DE INGRESO";
            case "EXPENSE" -> "COMPROBANTE DE EGRESO";
            case "TRANSFER_OUT" -> "COMPROBANTE DE TRANSFERENCIA";
            case "SAFE_DROP" -> "COMPROBANTE DE DEPÓSITO";
            default -> "COMPROBANTE DE CAJA";
        };
    }

    public static String cashMovementTemplate() {
        return """

[CENTER][BOLD]{{location_name}}[/BOLD][/CENTER]
[CENTER]{{location_address}}[/CENTER]
[CENTER]R.U.C.: {{location_ruc}}[/CENTER]
[CENTER]Teléfono: {{location_phone}}[/CENTER]
---
[CENTER][BOLD]{{movement_type}}[/BOLD][/CENTER]
---
Fecha: {{date}}
Hora: {{time}}
Usuario: {{user_name}}
---
Concepto: {{observation}}
---
[CENTER][BOLD]TOTAL:  ${{amount}}[/BOLD][/CENTER]
---
[CENTER]DOCUMENTO SIN VALIDEZ TRIBUTARIA[/CENTER]
[CENTER]COMPROBANTE INTERNO[/CENTER]""";
    }

    // ── Default template ─────────────────────────────────

    public static String defaultTemplate() {
        // Leading \n is filtered by render() skipBlankLines
        return """

[CENTER][BOLD]{{location_name}}[/BOLD][/CENTER]
[CENTER]{{location_address}}[/CENTER]
[CENTER]R.U.C.: {{location_ruc}}[/CENTER]
[CENTER]Dirección: {{location_address}}[/CENTER]
[CENTER]Teléfono: {{location_phone}}[/CENTER]
[CENTER]{{location_city}} - {{location_country}}[/CENTER]
[CENTER]{{fiscal_regime}}[/CENTER]
---
Fecha y Hora: {{date}}  {{time}}
{#invoice}Factura: {{invoice_id}}
Clave: {{invoice_auth}}
Ambiente: {{sri_environment}}  Emisión: {{emission_type}}
{/invoice}---
{#customer}Cliente: {{customer_name}}
CED/RUC: {{customer_id}}
{#customer_address}Dirección: {{customer_address}}
{/customer_address}Teléfono: {{customer_phone}}  Placa: {{plate}}
{#customer_email}Email: {{customer_email}}
{/customer_email}{/customer}---
Manguera: {{hose_id}}
Producto: {{grade}}
Cantidad: {{volume}} {{unit}}
Precio Sin Subsidio: $ {{price_without_subsidy}}
Subsidio: $ {{subsidy_per_unit}}
Precio Unitario: $ {{unit_price}}
Subtotal: $ {{subtotal}}
{{tax_label}}: $ {{tax_amount}}
===
[CENTER][BOLD]TOTAL:  ${{amount}}[/BOLD][/CENTER]
===
---
{#subsidy_amount}Valor Total Sin Subsidio: $ {{subsidy_amount}}
Ahorro Por Subsidio: $ {{subsidy_amount}}
---
{/subsidy_amount}[CENTER]DOCUMENTO CON VALIDEZ TRIBUTARIA[/CENTER]
[CENTER]Descarga de Factura en: www.sri.com.ec[/CENTER]
[CENTER]POWERFIN GAS[/CENTER]
[CENTER]GRACIAS POR SU COMPRA[/CENTER]""";
    }
}
