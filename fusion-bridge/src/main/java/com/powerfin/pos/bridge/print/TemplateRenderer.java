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
 */
@ApplicationScoped
public class TemplateRenderer {

    // ── ESC/POS commands ──────────────────────────────────
    private static final byte ESC = 0x1B;
    private static final byte GS  = 0x1D;
    private static final byte[] BOLD_ON   = { ESC, 'E', 1 };
    private static final byte[] BOLD_OFF  = { ESC, 'E', 0 };
    private static final byte[] ALIGN_LEFT   = { ESC, 'a', 0x00 };
    private static final byte[] ALIGN_CENTER = { ESC, 'a', 0x01 };
    private static final byte[] FONT_SMALL  = { ESC, 'M', 1 };
    private static final byte[] LINE_SPACING_0 = { ESC, '3', 0 };
    private static final byte[] CUT_FULL    = { GS, 'V', 0x00 };
    private static final byte[] LF = { '\n' };
    private static final int COLUMNS = 50;

    // ── Template storage ─────────────────────────────────
    private volatile String template;
    private final Path templateFile;
    private final String defaultTemplate;

    /** 7 dots at end of every ticket — prevents cutter from slicing text. */
    private static final String TRAILER_DOTS = ".\n.\n.\n.\n.\n.\n.";

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

    public void saveTemplate(String newTemplate) throws IOException {
        this.template = newTemplate;
        if (templateFile != null) {
            Files.createDirectories(templateFile.getParent());
            Files.writeString(templateFile, newTemplate, StandardCharsets.UTF_8);
            Log.infof("Template saved to %s", templateFile);
        }
    }

    // ── Render ───────────────────────────────────────────

    public byte[] render(ReceiptBuilder.FuelReceiptData data) {
        ByteArrayOutputStream out = new ByteArrayOutputStream();
        String[] lines = template.split("\n");

        try { out.write(FONT_SMALL); out.write(LINE_SPACING_0); } catch (IOException ignored) { }

        int i = 0;
        while (i < lines.length) {
            String line = lines[i];
            if (line.isBlank()) { i++; continue; }

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
            if (line.contains("{#reprint}")) {
                i = skipConditional(lines, i, "{#reprint}", "{/reprint}", data.isReprint, out, data);
                continue;
            }

            renderLine(out, line, data);
            i++;
        }

        // Feed paper then cut — LFs go through text buffer ensuring all text is printed
        try { writeCut(out); } catch (IOException ignored) { }
        return out.toByteArray();
    }

    // ── Internal ─────────────────────────────────────────

    /** Full paper cut. No extra feed — template provides trailing dots. */
    private static void writeCut(OutputStream out) throws IOException {
        out.write(CUT_FULL);
    }

    private int skipConditional(String[] lines, int start,
                                 String open, String close,
                                 boolean visible,
                                 OutputStream out,
                                 ReceiptBuilder.FuelReceiptData data) {
        int depth = 0;
        int i = start;
        while (i < lines.length) {
            String line = lines[i];
            int opens = countInLine(line, open);
            int closes = countInLine(line, close);
            depth += opens;

            if (depth > 0 && visible) {
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
            if (depth <= 0 && opens > 0) break;
            if (depth <= 0 && opens == 0 && i > start + 1) break;
        }
        return i;
    }

    private int countInLine(String line, String tag) {
        int count = 0;
        int idx = 0;
        while ((idx = line.indexOf(tag, idx)) >= 0) { count++; idx += tag.length(); }
        return count;
    }

    private void renderLine(OutputStream out, String line,
                             ReceiptBuilder.FuelReceiptData data) {
        try {
            if (line.trim().equals("[CUT]")) { writeCut(out); return; }

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

            line = resolve(line, data);

            boolean isThinSep  = line.trim().matches("-{3,}");
            boolean isBoldSep  = line.trim().matches("={3,}");

            if (isThinSep || isBoldSep) {
                out.write(LF);
                if (isBoldSep) out.write(BOLD_ON);
                out.write(repeat('-', COLUMNS));
                if (isBoldSep) out.write(BOLD_OFF);
                out.write(LF);
                return;
            }

            if (center) out.write(ALIGN_CENTER);
            if (bold) out.write(BOLD_ON);

            out.write(line.getBytes(StandardCharsets.UTF_8));
            out.write(LF);

            if (bold) out.write(BOLD_OFF);
            if (center) out.write(ALIGN_LEFT);

        } catch (IOException e) {
            Log.errorf("Template render error: %s", e.getMessage());
        }
    }

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
            .replace("{{unit}}", nvl(data.unit, "GAL"))
            .replace("{{shift_id}}", nvl(data.shiftId, ""))
            .replace("{{cashier_name}}", nvl(data.cashierName, ""));
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

    public byte[] renderCashMovement(ReceiptBuilder.CashMovementData data) {
        ByteArrayOutputStream out = new ByteArrayOutputStream();
        String[] lines = cashMovementTemplate().split("\n");

        try { out.write(FONT_SMALL); out.write(LINE_SPACING_0); } catch (IOException ignored) { }

        boolean inReprintBlock = false;
        for (String line : lines) {
            if (line.isBlank()) continue;

            // {#reprint} conditional — only show on reprints
            if (line.contains("{#reprint}")) {
                inReprintBlock = true;
                if (!data.isReprint) continue; // skip entire block
                line = line.replace("{#reprint}", "");
            }
            if (line.contains("{/reprint}")) {
                inReprintBlock = false;
                if (!data.isReprint) continue;
                line = line.replace("{/reprint}", "");
            }
            if (inReprintBlock && !data.isReprint) continue;
            if (line.isBlank()) continue;

            try {
                if (line.trim().equals("[CUT]")) { writeCut(out); continue; }

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

                resolved = resolved
                    .replace("{{location_name}}", nvl(data.locationName, "GASOLINERA"))
                    .replace("{{location_address}}", nvl(data.locationAddress, ""))
                    .replace("{{location_ruc}}", nvl(data.locationRuc, ""))
                    .replace("{{location_phone}}", nvl(data.locationPhone, ""))
                    .replace("{{movement_type}}", movementLabel(data.movementType))
                    .replace("{{movement_id}}", nvl(data.movementId, ""))
                    .replace("{{shift_id}}", nvl(data.shiftId, ""))
                    .replace("{{date}}", nvl(data.date, ""))
                    .replace("{{time}}", nvl(data.time, ""))
                    .replace("{{user_name}}", nvl(data.userName, ""))
                    .replace("{{amount}}", nvl(data.amount, "0.00"))
                    .replace("{{observation}}", nvl(data.observation, ""));

                boolean isSep = resolved.trim().matches("-{3,}") || resolved.trim().matches("={3,}");
                if (isSep) {
                    out.write(LF);
                    out.write(repeat('-', COLUMNS));
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

        try { writeCut(out); } catch (IOException ignored) { }
        return out.toByteArray();
    }

    // ── Shift close receipt ────────────────────────────

    public byte[] renderShiftClose(ReceiptBuilder.ShiftCloseData data) {
        ByteArrayOutputStream out = new ByteArrayOutputStream();
        String[] lines = shiftCloseTemplate().split("\n");

        try { out.write(FONT_SMALL); out.write(LINE_SPACING_0); } catch (IOException ignored) { }

        for (String line : lines) {
            if (line.isBlank()) continue;

            try {
                boolean bold = false, center = false;
                String resolved = line;

                while (resolved.contains("[BOLD]") && resolved.contains("[/BOLD]")) {
                    bold = true;
                    resolved = resolved.replace("[BOLD]", "").replace("[/BOLD]", "");
                }
                while (resolved.contains("[CENTER]") && resolved.contains("[/CENTER]")) {
                    center = true;
                    resolved = resolved.replace("[CENTER]", "").replace("[/CENTER]", "");
                }

                // Conditionals — handle both open and close tags
                if (resolved.contains("{#surplus}") || resolved.contains("{/surplus}")) {
                    if (data.surplus == null || data.surplus.isEmpty() || "0.00".equals(data.surplus)) continue;
                    resolved = resolved.replace("{#surplus}", "").replace("{/surplus}", "");
                    if (resolved.isBlank()) continue;
                }
                if (resolved.contains("{#shortage}") || resolved.contains("{/shortage}")) {
                    if (data.shortage == null || data.shortage.isEmpty() || "0.00".equals(data.shortage)) continue;
                    resolved = resolved.replace("{#shortage}", "").replace("{/shortage}", "");
                    if (resolved.isBlank()) continue;
                }
                if (resolved.contains("{#noncash}") || resolved.contains("{/noncash}")) {
                    if (data.nonCashLines == null || data.nonCashLines.isEmpty()) continue;
                    resolved = resolved.replace("{#noncash}", "").replace("{/noncash}", "");
                    if (resolved.isBlank()) continue;
                }

                resolved = resolved
                    .replace("{{location_name}}", nvl(data.locationName, "GASOLINERA"))
                    .replace("{{location_address}}", nvl(data.locationAddress, ""))
                    .replace("{{location_ruc}}", nvl(data.locationRuc, ""))
                    .replace("{{location_phone}}", nvl(data.locationPhone, ""))
                    .replace("{{date}}", nvl(data.date, ""))
                    .replace("{{time}}", nvl(data.time, ""))
                    .replace("{{user_name}}", nvl(data.userName, ""))
                    .replace("{{shift_id}}", nvl(data.shiftId, ""))
                    .replace("{{opened_at}}", nvl(data.openedAt, ""))
                    .replace("{{closed_at}}", nvl(data.closedAt, ""))
                    .replace("{{opening_cash}}", nvl(data.openingCash, "0.00"))
                    .replace("{{sales_cash}}", nvl(data.salesCash, "0.00"))
                    .replace("{{sales_cash_count}}", nvl(data.salesCashCount, "0"))
                    .replace("{{income}}", nvl(data.income, "0.00"))
                    .replace("{{income_count}}", nvl(data.incomeCount, "0"))
                    .replace("{{expense}}", nvl(data.expense, "0.00"))
                    .replace("{{expense_count}}", nvl(data.expenseCount, "0"))
                    .replace("{{deposits}}", nvl(data.deposits, "0.00"))
                    .replace("{{deposits_count}}", nvl(data.depositsCount, "0"))
                    .replace("{{transfers_out}}", nvl(data.transfersOut, "0.00"))
                    .replace("{{transfers_out_count}}", nvl(data.transfersOutCount, "0"))
                    .replace("{{transfers_in}}", nvl(data.transfersIn, "0.00"))
                    .replace("{{transfers_in_count}}", nvl(data.transfersInCount, "0"))
                    .replace("{{safe_drops}}", nvl(data.safeDrops, "0.00"))
                    .replace("{{safe_drops_count}}", nvl(data.safeDropsCount, "0"))
                    .replace("{{total_cash}}", nvl(data.totalCash, "0.00"))
                    .replace("{{total_sales}}", nvl(data.totalSales, "0.00"))
                    .replace("{{surplus}}", nvl(data.surplus, ""))
                    .replace("{{shortage}}", nvl(data.shortage, ""))
                    .replace("{{noncash_lines}}", nvl(data.nonCashLines, ""));

                boolean isSep = resolved.trim().matches("-{3,}") || resolved.trim().matches("={3,}");
                if (isSep) {
                    out.write(LF);
                    out.write(repeat('-', COLUMNS));
                    out.write(LF);
                    continue;
                }

                if (center) out.write(ALIGN_CENTER);
                if (bold) out.write(BOLD_ON);

                // {{DOT:label:value}} → "LABEL: ..... $ VALUE" with dot leaders
                if (resolved.contains("{{DOT:")) {
                    resolved = formatDottedLine(resolved);
                }

                out.write(resolved.getBytes(StandardCharsets.UTF_8));
                out.write(LF);
                if (bold) out.write(BOLD_OFF);
                if (center) out.write(ALIGN_LEFT);
            } catch (IOException e) {
                Log.errorf("Shift close render error: %s", e.getMessage());
            }
        }

        try { writeCut(out); } catch (IOException ignored) { }
        return out.toByteArray();
    }

    /** Format "{{DOT:label:value}}" → "LABEL: ..... $ VALUE" with dots to fill 48 chars. */
    private static String formatDottedLine(String line) {
        java.util.regex.Matcher m = java.util.regex.Pattern.compile("\\{\\{DOT:([^:]+):([^}]+)\\}\\}").matcher(line);
        StringBuffer sb = new StringBuffer();
        while (m.find()) {
            String label = m.group(1).trim();
            String value = m.group(2).trim();
            String full = label + ": $" + value;
            int dots = 48 - full.length();
            if (dots > 0) full = label + ": " + ".".repeat(dots) + "$" + value;
            m.appendReplacement(sb, java.util.regex.Matcher.quoteReplacement(full));
        }
        m.appendTail(sb);
        return sb.toString();
    }

    public static String shiftCloseTemplate() {
        return """

[CENTER][BOLD]{{location_name}}[/BOLD][/CENTER]
[CENTER]{{location_address}}[/CENTER]
[CENTER]R.U.C.: {{location_ruc}}[/CENTER]
[CENTER]TELEFONO: {{location_phone}}[/CENTER]
---
[CENTER][BOLD]CIERRE DE TURNO[/BOLD][/CENTER]
---
FECHA: {{date}}  HORA: {{time}}
USUARIO: {{user_name}}
TURNO: #{{shift_id}}
APERTURA: {{opened_at}}
CIERRE: {{closed_at}}
---
[CENTER][BOLD]RESUMEN DE EFECTIVO[/BOLD][/CENTER]
---
{{DOT:(+) APERTURA: {{opening_cash}}}}
{{DOT:(+) VENTAS EFECTIVO ({{sales_cash_count}}): {{sales_cash}}}}
{{DOT:(+) INGRESOS ({{income_count}}): {{income}}}}
{{DOT:(-) EGRESOS ({{expense_count}}): {{expense}}}}
{{DOT:(-) DEPOSITOS ({{deposits_count}}): {{deposits}}}}
{{DOT:(-) TRANSF. ENVIADAS ({{transfers_out_count}}): {{transfers_out}}}}
{{DOT:(+) TRANSF. RECIBIDAS ({{transfers_in_count}}): {{transfers_in}}}}
---
{{DOT:TOTAL EFECTIVO: {{total_cash}}}}
---
{#surplus}[CENTER]SOBRANTE: $ {{surplus}}[/CENTER]
{/surplus}
{#shortage}[CENTER]FALTANTE: $ {{shortage}}[/CENTER]
{/shortage}
---
{#noncash}[CENTER][BOLD]OTRAS FORMAS DE PAGO[/BOLD][/CENTER]
---
{{noncash_lines}}
---
{/noncash}
[CENTER][BOLD]TOTAL VENTAS DEL TURNO: $ {{total_sales}}[/BOLD][/CENTER]
---
[CENTER]POWERFIN GAS[/CENTER]
.
.
.
.
.
.
.""";
    }

    private static String movementLabel(String type) {
        if (type == null) return "";
        return switch (type.toUpperCase()) {
            case "INCOME" -> "COMPROBANTE DE INGRESO";
            case "EXPENSE" -> "COMPROBANTE DE EGRESO";
            case "TRANSFER_OUT" -> "COMPROBANTE DE TRANSFERENCIA";
            case "SAFE_DROP" -> "COMPROBANTE DE DEPOSITO";
            case "DEPOSIT" -> "COMPROBANTE DE DEPOSITO";
            default -> "COMPROBANTE DE CAJA";
        };
    }

    public static String cashMovementTemplate() {
        return """

{#reprint}[CENTER][BOLD]*** REIMPRESION ***[/BOLD][/CENTER]
{/reprint}
[CENTER][BOLD]{{location_name}}[/BOLD][/CENTER]
[CENTER]{{location_address}}[/CENTER]
[CENTER]R.U.C.: {{location_ruc}}[/CENTER]
[CENTER]TELEFONO: {{location_phone}}[/CENTER]
---
[CENTER][BOLD]{{movement_type}}[/BOLD][/CENTER]
---
TRANSACCION: {{movement_id}}
TURNO:       {{shift_id}}
FECHA: {{date}}
HORA: {{time}}
USUARIO: {{user_name}}
---
CONCEPTO: {{observation}}
---
[CENTER][BOLD]TOTAL:  ${{amount}}[/BOLD][/CENTER]
---
[CENTER]DOCUMENTO SIN VALIDEZ TRIBUTARIA[/CENTER]
[CENTER]COMPROBANTE INTERNO[/CENTER]
.
.
.
.
.
.
.""";
    }

    // ── Default template ─────────────────────────────────

    public static String defaultTemplate() {
        return """

{#reprint}[CENTER][BOLD]*** REIMPRESION ***[/BOLD][/CENTER]
{/reprint}
[CENTER][BOLD]{{location_name}}[/BOLD][/CENTER]
[CENTER]R.U.C.: {{location_ruc}}[/CENTER]
[CENTER]DIRECCION: {{location_address}}[/CENTER]
[CENTER]TELEFONO: {{location_phone}}[/CENTER]
[CENTER]{{location_city}} - {{location_country}}[/CENTER]
[CENTER]{{fiscal_regime}}[/CENTER]
---
FECHA Y HORA: {{date}}  {{time}}
{#invoice}FACTURA: {{invoice_id}}
CLAVE: {{invoice_auth}}
AMBIENTE: {{sri_environment}}  EMISION: {{emission_type}}
{/invoice}---
{#customer}CLIENTE: {{customer_name}}
CED/RUC: {{customer_id}}
{#customer_address}DIRECCION: {{customer_address}}
{/customer_address}TELEFONO: {{customer_phone}}  PLACA: {{plate}}
{#customer_email}EMAIL: {{customer_email}}
{/customer_email}{/customer}---
TURNO: {{shift_id}}  CAJERO: {{cashier_name}}
---
MANGUERA: {{hose_id}}
PRODUCTO: {{grade}}
CANTIDAD: {{volume}} {{unit}}
PRECIO SIN SUBSIDIO: $ {{price_without_subsidy}}
SUBSIDIO: $ {{subsidy_per_unit}}
PRECIO UNITARIO: $ {{unit_price}}
SUBTOTAL: $ {{subtotal}}
{{tax_label}}: $ {{tax_amount}}
===
[CENTER][BOLD]TOTAL:  ${{amount}}[/BOLD][/CENTER]
===
FORMA DE PAGO: {{payment_method}}
---
{#subsidy_amount}VALOR TOTAL SIN SUBSIDIO: $ {{amount}}
AHORRO POR SUBSIDIO: $ {{subsidy_amount}}
---
{/subsidy_amount}[CENTER]DOCUMENTO CON VALIDEZ TRIBUTARIA[/CENTER]
[CENTER]DESCARGA DE FACTURA EN: www.sri.com.ec[/CENTER]
[CENTER]POWERFIN GAS[/CENTER]
[CENTER]GRACIAS POR SU COMPRA[/CENTER]
.
.
.
.
.
.
.""";
    }
}
