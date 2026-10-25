package com.jamarglex.manijero.design

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.ExposedDropdownMenuBox
import androidx.compose.material3.ExposedDropdownMenuDefaults
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.ExposedDropdownMenuAnchorType
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.semantics.error
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.tooling.preview.Preview
import com.jamarglex.manijero.theme.ManijeroIconSize
import com.jamarglex.manijero.theme.ManijeroSpacing
import com.jamarglex.manijero.theme.ManijeroTheme
import manijero.shared.generated.resources.Res
import manijero.shared.generated.resources.ic_clear
import manijero.shared.generated.resources.ic_search

/**
 * A labelled single-line search field with a decorative leading magnifier.
 *
 * The field reports every keystroke and performs no filtering, accent folding, debouncing, or
 * history. When the caller's value is non-blank it shows a clear `IconButton` named by
 * [clearDescription] with Material's 48 dp target; the button reports an empty string, which is the
 * caller's cue to clear its own state.
 */
@Composable
internal fun ManijeroSearchField(
    value: String,
    onValueChange: (String) -> Unit,
    label: String,
    clearDescription: String,
    modifier: Modifier = Modifier,
    placeholder: String? = null,
) {
    val clearButton: (@Composable () -> Unit)? = if (value.isNotBlank()) {
        {
            IconButton(onClick = { onValueChange("") }) {
                ManijeroIcon(
                    resource = Res.drawable.ic_clear,
                    contentDescription = clearDescription,
                    size = ManijeroIconSize.Inline,
                )
            }
        }
    } else {
        null
    }

    OutlinedTextField(
        value = value,
        onValueChange = onValueChange,
        modifier = modifier.fillMaxWidth(),
        label = { Text(text = label) },
        placeholder = placeholder?.let { text -> { Text(text = text) } },
        leadingIcon = {
            ManijeroIcon(
                resource = Res.drawable.ic_search,
                contentDescription = null,
                size = ManijeroIconSize.Inline,
            )
        },
        trailingIcon = clearButton,
        singleLine = true,
    )
}

/**
 * A labelled read-only field that exposes the caller's options in a Material exposed dropdown.
 *
 * The field shows [selected] or [placeholder], reports the chosen option through [onSelect], and
 * exposes [isError] plus [supportingText]. It keeps no selection of its own, filters nothing, and
 * adds no option: the list is exactly the caller's.
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
internal fun ManijeroDropdownField(
    label: String,
    options: List<String>,
    selected: String?,
    onSelect: (String) -> Unit,
    modifier: Modifier = Modifier,
    placeholder: String? = null,
    isError: Boolean = false,
    supportingText: String? = null,
) {
    var expanded by remember { mutableStateOf(false) }

    ExposedDropdownMenuBox(
        expanded = expanded,
        onExpandedChange = { expanded = it },
        modifier = modifier.fillMaxWidth(),
    ) {
        OutlinedTextField(
            value = selected.orEmpty(),
            onValueChange = {},
            readOnly = true,
            modifier = Modifier
                .fillMaxWidth()
                .menuAnchor(ExposedDropdownMenuAnchorType.PrimaryNotEditable),
            label = { Text(text = label) },
            placeholder = placeholder?.let { text -> { Text(text = text) } },
            trailingIcon = { ExposedDropdownMenuDefaults.TrailingIcon(expanded = expanded) },
            isError = isError,
            supportingText = supportingText?.let { text -> { Text(text = text) } },
            singleLine = true,
        )
        ExposedDropdownMenu(expanded = expanded, onDismissRequest = { expanded = false }) {
            options.forEach { option ->
                DropdownMenuItem(
                    text = { Text(text = option) },
                    onClick = {
                        expanded = false
                        onSelect(option)
                    },
                )
            }
        }
    }
}

/**
 * A labelled measure field: it renders and reports the caller's text verbatim.
 *
 * [keyboardType] only asks the platform keyboard for the right layout. The component performs no
 * parsing, rounding, unit conversion, or inference; [errorText] both marks the field as errored and
 * becomes its supporting text, and [supportingText] is the neutral helper when there is no error.
 * The caller keeps the entered value unchanged.
 */
@Composable
internal fun ManijeroMeasureField(
    value: String,
    onValueChange: (String) -> Unit,
    label: String,
    modifier: Modifier = Modifier,
    supportingText: String? = null,
    errorText: String? = null,
    keyboardType: KeyboardType = KeyboardType.Decimal,
) {
    val supporting = errorText ?: supportingText
    OutlinedTextField(
        value = value,
        onValueChange = onValueChange,
        modifier = modifier
            .fillMaxWidth()
            .semantics { errorText?.let { message -> error(message) } },
        label = { Text(text = label) },
        singleLine = true,
        keyboardOptions = KeyboardOptions(keyboardType = keyboardType),
        isError = errorText != null,
        supportingText = supporting?.let { text -> { Text(text = text) } },
    )
}

@Composable
private fun ManijeroFieldsPreviewContent() {
    var search by remember { mutableStateOf("olivar") }
    var measure by remember { mutableStateOf("1,5") }

    Column(verticalArrangement = Arrangement.spacedBy(ManijeroSpacing.Small)) {
        ManijeroSearchField(
            value = search,
            onValueChange = { search = it },
            label = "Buscar terreno",
            clearDescription = "Borrar la búsqueda",
        )
        ManijeroSearchField(
            value = "",
            onValueChange = {},
            label = "Buscar terreno",
            clearDescription = "Borrar la búsqueda",
            placeholder = "Nombre o municipio",
        )
        ManijeroDropdownField(
            label = "Variedad",
            options = listOf("Picual", "Hojiblanca", "Otra"),
            selected = "Picual",
            onSelect = {},
        )
        ManijeroDropdownField(
            label = "Variedad",
            options = listOf("Picual", "Hojiblanca", "Otra"),
            selected = null,
            onSelect = {},
            placeholder = "Elige una variedad",
            isError = true,
            supportingText = "Elige una variedad para continuar.",
        )
        ManijeroMeasureField(
            value = measure,
            onValueChange = { measure = it },
            label = "Superficie (ha)",
            supportingText = "Opcional. Puedes dejarlo en blanco.",
        )
        ManijeroMeasureField(
            value = "",
            onValueChange = {},
            label = "Número de árboles",
            errorText = "Escribe solo números, sin letras.",
        )
    }
}

@Composable
private fun ManijeroFieldsPreviewFrame(dark: Boolean) {
    ManijeroTheme(darkTheme = dark) {
        Surface(color = MaterialTheme.colorScheme.background) {
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(ManijeroSpacing.Small),
            ) { ManijeroFieldsPreviewContent() }
        }
    }
}

@Preview(name = "ManijeroFields — claro", widthDp = 380)
@Composable
private fun ManijeroFieldsLightPreview() = ManijeroFieldsPreviewFrame(dark = false)

@Preview(name = "ManijeroFields — oscuro", widthDp = 380)
@Composable
private fun ManijeroFieldsDarkPreview() = ManijeroFieldsPreviewFrame(dark = true)

@Preview(name = "ManijeroFields — texto grande", widthDp = 360, fontScale = 2f)
@Composable
private fun ManijeroFieldsLargeTextPreview() = ManijeroFieldsPreviewFrame(dark = false)
